"""PatchPilot 证据检索层：Tavily 检索 → 确定性闸门 → 可引用证据。

设计立场（与全项目一致）：

    Tavily proposes. The gate decides what counts as evidence.

检索回来的网页只是**候选**。能不能进入审查回执，由确定性规则裁决：
域名分级、关键词必中、去重、打分、以及最关键的一步——把候选片段里的
关键词拿去 `extract` 下来的正文中核对（quote verification）。核对不上的，
即使来自权威站点也标 `quote_verified=False`，绝不冒充"已验证引用"。

覆盖的 Tavily 端点（零依赖，纯 urllib）：
    POST /search      主检索（topic / search_depth / include_domains / time_range）
    POST /extract     拉正文，用于引用核对
    POST /map         站点地图，用于定位官方文档的权威页面
    POST /crawl       域内遍历（默认关闭，需显式开 `--deep`）
    POST /research    深度研究任务（默认关闭，异步轮询）
    GET  /usage       key 用量，用于预算对账

断网/无 Key 时永不崩溃：可切到 `--offline-evidence`，返回内置 fixture，
让演示与视频永远有内容可讲。
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

DEFAULT_BASE = "https://api.tavily.com"

# --------------------------------------------------------------------------
# 信任分级：权威源优先，内容农场出局
# --------------------------------------------------------------------------

TIER1 = 3   # 官方 / 标准 / 权威数据库
TIER2 = 1   # 社区 / 博客
TIER3 = 0   # 其他

_TIER1_DOMAINS = {
    "nvd.nist.gov", "cve.org", "cwe.mitre.org", "owasp.org",
    "docs.python.org", "peps.python.org", "python.org",
    "github.com", "github.blog", "security.gentoo.org",
    "cheatsheetseries.owasp.org", "docs.github.com",
    "bandit.readthedocs.io", "pypi.org",
}

_TIER2_DOMAINS = {
    "stackoverflow.com", "stackexchange.com", "realpython.com",
    "dev.to", "medium.com", "reddit.com", "news.ycombinator.com",
    "snyk.io", "safetycli.com", "blog.python.org",
}

# 内容农场 / 采集站：一律不进回执
_BLOCKED_SUBSTRINGS = (
    "pinterest.", "quora.", "zhihu.com", "baidu.com", "csdn.net",
    "jianshu.com", "cnblogs.com", "iteye.com", "51cto.com",
    "seowebsite", "-blogs.com", "articlesfactory",
)


def tier_label(tier: int) -> str:
    """把数字档位显示成人能读的等级（A 权威 / B 社区 / C 其他 / X 屏蔽）。"""
    return {TIER1: "A", TIER2: "B", TIER3: "C", -1: "X"}.get(tier, "C")


def domain_of(url: str) -> str:
    """URL → 归一化域名（去 www / 端口 / 大小写）。"""
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except ValueError:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host.split(":")[0]


def tier_of(url: str) -> int:
    host = domain_of(url)
    if not host:
        return TIER3
    if any(b in host for b in _BLOCKED_SUBSTRINGS):
        return -1
    if host in _TIER1_DOMAINS:
        return TIER1
    if host in _TIER2_DOMAINS:
        return TIER2
    # 官方文档子域（docs.*.io / *.readthedocs.io）视为权威
    if host.endswith(".readthedocs.io") or ".readthedocs.io" in host:
        return TIER1
    if host.startswith("docs.") or ".docs." in host:
        return TIER2
    return TIER3


# --------------------------------------------------------------------------
# 检索意图：由 finding 的 code 确定性推导，不靠 LLM 拼查询
# --------------------------------------------------------------------------

# intent -> (topic, search_depth, 默认域名白名单, 查询后缀)
INTENTS: Dict[str, dict] = {
    "cve_advisory": {
        "topic": "news",
        "depth": "advanced",
        "domains": ["nvd.nist.gov", "cve.org", "cwe.mitre.org", "owasp.org",
                    "github.com", "github.blog"],
        "suffix": "vulnerability advisory remediation",
        "must": ("cve", "vulnerab", "exploit", "advisory", "security", "injection"),
    },
    "official_doc": {
        "topic": "general",
        "depth": "basic",
        "domains": ["docs.python.org", "peps.python.org", "python.org"],
        "suffix": "official documentation recommended",
        "must": ("python", "documentation", "reference", "howto", "pep", "recommend"),
    },
    "best_practice": {
        "topic": "general",
        "depth": "basic",
        "domains": ["docs.python.org", "realpython.com", "stackoverflow.com",
                    "owasp.org", "cheatsheetseries.owasp.org"],
        "suffix": "best practice why avoid",
        "must": ("python", "best", "practice", "avoid", "instead", "logging", "why"),
    },
}

# finding code -> intent；未列出的 code 不消耗检索预算（TODO_FIXME 之类不值得查）
CODE_INTENT: Dict[str, str] = {
    "EVAL_EXEC": "cve_advisory",
    "HARDCODED_SECRET": "cve_advisory",
    "BARE_EXCEPT": "official_doc",
    "EQ_NONE": "official_doc",
    "EQ_BOOL": "official_doc",
    "TYPE_EQ": "official_doc",
    "MUTABLE_DEFAULT": "official_doc",
    "IMPORT_STAR": "official_doc",
    "PRINT_DEBUG": "best_practice",
}

# code -> 检索主体（人类词，不是正则）
CODE_SUBJECT: Dict[str, str] = {
    "EVAL_EXEC": "python eval exec arbitrary code execution",
    "HARDCODED_SECRET": "hardcoded credentials secret in source code leak",
    "BARE_EXCEPT": "python bare except clause",
    "EQ_NONE": "python compare None is vs equals",
    "EQ_BOOL": "python compare boolean with == True",
    "TYPE_EQ": "python type equality vs isinstance",
    "MUTABLE_DEFAULT": "python mutable default argument",
    "IMPORT_STAR": "python from module import star",
    "PRINT_DEBUG": "python print vs logging",
}


def plan_queries(finding) -> Optional[dict]:
    """为一条 finding 生成确定性检索计划。无可用的意图则返回 None（不花钱）。"""
    code = str(getattr(finding, "code", "")).upper()
    intent = CODE_INTENT.get(code)
    if not intent:
        return None
    spec = INTENTS[intent]
    subject = CODE_SUBJECT.get(code, (getattr(finding, "rule", "") or code))
    return {
        "code": code,
        "intent": intent,
        "query": f"{subject} {spec['suffix']}".strip(),
        "params": {
            "topic": spec["topic"],
            "search_depth": spec["depth"],
            "include_domains": list(spec["domains"]),
            "include_domains_mode": "filter",
            "max_results": 5,
            "include_answer": False,
            "include_raw_content": False,
            "include_usage": True,
        },
        "must": spec["must"],
    }


# --------------------------------------------------------------------------
# Tavily 客户端（五个端点，零依赖）
# --------------------------------------------------------------------------

class TavilyError(Exception):
    pass


class TavilyClient:
    """Tavily REST 客户端。每个端点都计数、计时，失败抛 TavilyError。"""

    def __init__(self, api_key: str, base: str = DEFAULT_BASE, timeout: int = 30) -> None:
        self.api_key = api_key
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.calls: Dict[str, int] = {}
        self.credits: float = 0.0
        self.errors: List[str] = []

    # -- plumbing ---------------------------------------------------------
    def _post(self, path: str, body: dict, method: str = "POST") -> dict:
        url = f"{self.base}{path}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            raise TavilyError(f"{method} {path} -> HTTP {exc.code} {detail}") from exc
        except Exception as exc:  # 网络层任何问题都归一
            raise TavilyError(f"{method} {path} -> {type(exc).__name__}: {exc}") from exc
        self.calls[path] = self.calls.get(path, 0) + 1
        usage = payload.get("usage") or {}
        try:
            self.credits += float(usage.get("credits", 0) or 0)
        except (TypeError, ValueError):
            pass
        return payload

    # -- endpoints --------------------------------------------------------
    def search(self, query: str, **params) -> dict:
        body = {"query": query}
        body.update(params)
        return self._post("/search", body)

    def extract(self, urls: List[str], query: str = "", **params) -> dict:
        body = {"urls": urls, "query": query, "format": "markdown",
                "extract_depth": "basic"}
        body.update(params)
        return self._post("/extract", body)

    def map(self, url: str, **params) -> dict:
        body = {"url": url}
        body.update(params)
        return self._post("/map", body)

    def crawl(self, url: str, instructions: str = "", **params) -> dict:
        body = {"url": url, "instructions": instructions, "chunks_per_source": 3,
                "max_depth": 1, "limit": 20}
        body.update(params)
        return self._post("/crawl", body)

    def research(self, query: str, **params) -> dict:
        """创建深度研究任务（异步）。返回体通常带 request_id。"""
        body = {"query": query}
        body.update(params)
        return self._post("/research", body)

    def research_get(self, request_id: str) -> dict:
        return self._post(f"/research/{request_id}", {}, method="GET")

    def usage(self) -> dict:
        return self._post("/usage", {}, method="GET")


# --------------------------------------------------------------------------
# 确定性闸门
# --------------------------------------------------------------------------

def _norm(url: str) -> str:
    """URL 归一化，用于去重（去 fragment / 尾斜杠 / 查询串顺序敏感项）。"""
    try:
        p = urllib.parse.urlparse(url)
    except ValueError:
        return url
    q = urllib.parse.parse_qsl(p.query)
    q = sorted((k, v) for k, v in q if k not in ("utm_source", "utm_medium",
                                                 "utm_campaign", "ref", "source"))
    return urllib.parse.urlunparse((p.scheme, p.netloc.lower(),
                                    p.path.rstrip("/") or "/",
                                    "", urllib.parse.urlencode(q), ""))


def _score(item: dict, must: Tuple[str, ...]) -> Tuple[int, int]:
    """返回 (score, keyword_hits)。纯算术，无网络。"""
    text = (f"{item.get('title', '')} {item.get('content', '')}").lower()
    hits = sum(1 for k in must if k in text)
    tier = item.get("_tier", TIER3)
    score = tier * 10 + hits * 3
    if re.search(r"\bcve-\d{4}-\d{4,7}\b", text):
        score += 8
    if re.search(r"\bcwe-\d+\b", text):
        score += 5
    if re.search(r"\b(20[12]\d)\b", item.get("content", "")):
        score += 1                      # 有年份，较可能是近期资料
    score += min(len(item.get("content", "")) // 200, 3)
    return score, hits


class EvidenceGate:
    """裁决检索结果能否成为证据。规则写死，不看模型脸色。"""

    def __init__(self, min_tier: int = TIER2, min_hits: int = 1,
                 top_k: int = 2) -> None:
        self.min_tier = min_tier
        self.min_hits = min_hits
        self.top_k = top_k

    def admit(self, results: List[dict], must: Tuple[str, ...],
              seen: Optional[set] = None) -> Tuple[List[dict], List[dict]]:
        """返回 (admitted, rejected)。rejected 每条带 why，用于可解释性。"""
        seen = seen if seen is not None else set()
        admitted: List[dict] = []
        rejected: List[dict] = []
        for item in results:
            url = str(item.get("url", "") or "")
            if not url.startswith("http"):
                rejected.append({"url": url, "why": "not an http(s) url"})
                continue
            tier = tier_of(url)
            if tier < 0:
                rejected.append({"url": url, "why": "blocked domain (content farm)"})
                continue
            key = _norm(url)
            if key in seen:
                rejected.append({"url": url, "why": "duplicate url"})
                continue
            if tier < self.min_tier:
                rejected.append({"url": url, "why": f"tier {tier} below minimum {self.min_tier}"})
                continue
            score, hits = _score(item, must)
            if hits < self.min_hits:
                rejected.append({"url": url, "why": f"no required keyword (hits={hits})"})
                continue
            seen.add(key)
            admitted.append({
                "title": str(item.get("title", ""))[:180],
                "url": url,
                "domain": domain_of(url),
                "tier": tier,
                "snippet": str(item.get("content", ""))[:400],
                "score": score,
                "keyword_hits": hits,
                "tavily_score": item.get("score"),
                "quote_verified": False,
            })
        admitted.sort(key=lambda d: (-d["score"], d["url"]))
        return admitted[:self.top_k], rejected


def verify_quote(client: TavilyClient, evidence: dict, must: Tuple[str, ...],
                 timeout_ok: bool = True) -> dict:
    """把候选片段里的关键词拿去正文中核对。核对不上就不算已验证引用。"""
    if not timeout_ok:
        return evidence
    words = [w for w in re.findall(r"[A-Za-z]{5,}", evidence.get("snippet", ""))]
    probes = sorted(set(w.lower() for w in words), key=len, reverse=True)[:3]
    if not probes:
        return evidence
    try:
        payload = client.extract([evidence["url"]], query=evidence.get("title", ""))
    except TavilyError:
        return evidence
    body = ""
    for r in payload.get("results", []) or []:
        if r.get("url") == evidence["url"]:
            body = (r.get("raw_content") or "").lower()
            break
    if not body:
        return evidence
    matched = sum(1 for p in probes if p in body)
    evidence["quote_probes"] = probes
    evidence["quote_matched"] = matched
    evidence["quote_verified"] = matched >= max(1, len(probes) - 1)
    return evidence


# --------------------------------------------------------------------------
# 离线 fixture：断网也能演示
# --------------------------------------------------------------------------

FIXTURES: Dict[str, list] = {
    "EVAL_EXEC": [{
        "title": "CWE-95: Improper Neutralization of Directives in Dynamically "
                 "Evaluated Code ('Eval Injection')",
        "url": "https://cwe.mitre.org/data/definitions/95.html",
        "domain": "cwe.mitre.org", "tier": TIER1, "score": 41, "keyword_hits": 3,
        "snippet": "The product receives input from an upstream component, but it does "
                   "not neutralize or incorrectly neutralizes code syntax before "
                   "passing the input to a dynamic evaluation call such as eval().",
        "quote_verified": False, "fixture": True,
    }],
    "HARDCODED_SECRET": [{
        "title": "CWE-798: Use of Hard-coded Credentials",
        "url": "https://cwe.mitre.org/data/definitions/798.html",
        "domain": "cwe.mitre.org", "tier": TIER1, "score": 40, "keyword_hits": 3,
        "snippet": "The product contains hard-coded credentials, such as a password or "
                   "cryptographic key, which it uses for its own inbound authentication.",
        "quote_verified": False, "fixture": True,
    }],
    "BARE_EXCEPT": [{
        "title": "Errors and Exceptions - Python documentation",
        "url": "https://docs.python.org/3/tutorial/errors.html",
        "domain": "docs.python.org", "tier": TIER1, "score": 33, "keyword_hits": 2,
        "snippet": "The try statement works as follows: first, the try clause is "
                   "executed. If no exception occurs, the except clause is skipped.",
        "quote_verified": False, "fixture": True,
    }],
    "PRINT_DEBUG": [{
        "title": "Logging HOWTO - Python documentation",
        "url": "https://docs.python.org/3/howto/logging.html",
        "domain": "docs.python.org", "tier": TIER1, "score": 34, "keyword_hits": 3,
        "snippet": "Logging is a means of tracking events that happen when some "
                   "software runs. Use the logging module instead of print for "
                   "diagnostics that must survive into production.",
        "quote_verified": False, "fixture": True,
    }],
}


def fixture_evidence(findings: List) -> List[dict]:
    out: List[dict] = []
    for f in findings:
        for item in FIXTURES.get(str(getattr(f, "code", "")).upper(), []):
            out.append({**item, "for": getattr(f, "code", ""),
                        "intent": CODE_INTENT.get(str(getattr(f, "code", "")).upper(), "official_doc")})
    return out


# --------------------------------------------------------------------------
# 证据检索层
# --------------------------------------------------------------------------

class ResearchLayer:
    """把 findings 变成带证据的 findings。预算可控，失败可降级。"""

    def __init__(self, client: Optional[TavilyClient] = None,
                 max_search: int = 4, max_extract: int = 2,
                 offline: bool = False) -> None:
        self.client = client
        self.max_search = max_search
        self.max_extract = max_extract
        self.offline = offline

    @classmethod
    def from_env(cls, offline: bool = False) -> "ResearchLayer":
        key = os.environ.get("TAVILY_API_KEY")
        if offline or not key:
            return cls(client=None, offline=True)
        try:
            return cls(client=TavilyClient(key))
        except Exception:
            return cls(client=None, offline=True)

    @property
    def mode(self) -> str:
        if self.offline or self.client is None:
            return "offline-fixture"
        return "tavily"

    def enrich(self, findings: List) -> dict:
        """返回证据包。永远不抛异常——审查本身不能被检索拖垮。"""
        started = time.time()
        gate = EvidenceGate()
        bundle: dict = {
            "mode": self.mode,
            "evidence": [],
            "gate": {"considered": 0, "admitted": 0, "rejected": []},
            "calls": {},
            "credits": 0.0,
            "degraded": False,
            "reason": None,
            "elapsed_s": 0.0,
        }

        if self.mode == "offline-fixture":
            bundle["evidence"] = fixture_evidence(findings)
            bundle["gate"] = {"considered": len(bundle["evidence"]),
                              "admitted": len(bundle["evidence"]), "rejected": []}
            bundle["degraded"] = True
            bundle["reason"] = ("TAVILY_API_KEY 未设置或 --offline-evidence："
                                "使用内置 fixture，仅供演示，引用未经核对。")
            bundle["elapsed_s"] = round(time.time() - started, 3)
            return bundle

        assert self.client is not None
        seen: set = set()
        searches = 0
        extracts = 0
        errors: List[str] = []

        # 高危优先：预算花在最值得取证的问题上
        ordered = sorted(findings, key=lambda f: (
            0 if str(getattr(f, "severity", "")).upper() == "HIGH" else 1))

        for f in ordered:
            if searches >= self.max_search:
                break
            plan = plan_queries(f)
            if not plan:
                continue
            try:
                payload = self.client.search(plan["query"], **plan["params"])
            except TavilyError as exc:
                errors.append(str(exc))
                continue
            finally:
                searches += 1

            results = payload.get("results", []) or []
            bundle["gate"]["considered"] += len(results)
            admitted, rejected = gate.admit(results, tuple(plan["must"]), seen)
            for r in rejected:
                bundle["gate"]["rejected"].append({"for": plan["code"], **r})

            for ev in admitted:
                if extracts < self.max_extract:
                    ev = verify_quote(self.client, ev, tuple(plan["must"]))
                    extracts += 1
                ev["for"] = plan["code"]
                ev["intent"] = plan["intent"]
                bundle["evidence"].append(ev)

        bundle["gate"]["admitted"] = len(bundle["evidence"])
        bundle["calls"] = dict(self.client.calls)
        bundle["credits"] = round(self.client.credits, 2)
        if errors:
            bundle["degraded"] = True
            bundle["reason"] = f"部分检索失败（{len(errors)} 次）：{errors[0][:160]}"
        elif bundle["gate"]["admitted"] == 0:
            bundle["degraded"] = True
            bundle["reason"] = "检索未产出通过闸门的证据（全部被域名分级或关键词规则拒绝）。"
        bundle["elapsed_s"] = round(time.time() - started, 3)
        return bundle
