#!/usr/bin/env python3
"""PatchPilot 离线自测断言套件（零依赖，python eval.py）。

覆盖：离线 Linter 全规则触发、机械补丁生成、智能体闭环（离线模式）、
负测试（干净代码 0 发现）、双大脑去重、HTML 回执渲染。
有 NEBIUS_API_KEY 时可额外验证 Nemotron 通路（无则跳过，不影响通过）。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from patchpilot import OfflineLinter, PatchPilot  # noqa: E402
from patchpilot.receipts import html_receipt, text_receipt  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
_passed = 0
_failed = 0


def check(name, cond, extra=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  [PASS] {name}")
    else:
        _failed += 1
        print(f"  [FAIL] {name}  {extra}")


with open(os.path.join(_HERE, "examples", "bad_code.py"), encoding="utf-8") as f:
    BAD = f.read()

CLEAN = '''import os


def greet(name):
    if name is None:
        return "hello"
    return "hello " + name
'''

print("== 1. 离线 Linter 全规则触发 ==")
linter = OfflineLinter()
findings = linter.lint(BAD)
codes = {f.code for f in findings}
for expect in ["BARE_EXCEPT", "EVAL_EXEC", "HARDCODED_SECRET", "EQ_NONE",
               "MUTABLE_DEFAULT", "IMPORT_STAR", "EQ_BOOL", "TYPE_EQ",
               "PRINT_DEBUG", "TODO_FIXME", "LONG_LINE", "SWALLOWED_EXCEPT"]:
    check(f"lint.{expect}", expect in codes, sorted(codes))
check("lint.findings_have_evidence_or_source",
      all(f.source == "offline" for f in findings))
check("lint.hardcoded_secret_has_line", any(f.code == "HARDCODED_SECRET" and f.line > 0
                                            for f in findings))

print("== 2. 机械补丁 ==")
patches = linter.suggest_patches(BAD, findings)
pcodes = {p.line for p in patches}
check("patch.produced", len(patches) >= 2, len(patches))
check("patch.eq_none", any(p.before.strip().endswith("== None:") or "== None" in p.before
                           and "is None" in p.after for p in patches))
check("patch.bare_except", any("except Exception:" in p.after for p in patches))

print("== 3. 智能体闭环（离线模式） ==")
dp = PatchPilot(reviewer=None, search=None)
r = dp.review(BAD, use_llm=True)
check("agent.ok", r["ok"] is True)
check("agent.brain_offline", r["brain"] == "offline", r["brain"])
check("agent.nemotron_off", r["nemotron_used"] is False)
check("agent.band_high", r["band"] == "HIGH", r["band"])
check("agent.score>=30", r["score"] >= 30, r["score"])
check("agent.findings_nonempty", len(r["findings"]) >= 8, len(r["findings"]))
check("agent.explain_nonempty", bool(r["explain"].strip()))
check("agent.patches_present", len(r["patches"]) >= 2)

print("== 4. 负测试：干净代码 0 发现 ==")
rc = dp.review(CLEAN)
check("clean.ok", rc["ok"] is True)
check("clean.no_findings", len(rc["findings"]) == 0, [f["code"] for f in rc["findings"]])
check("clean.score_0", rc["score"] == 0, rc["score"])
check("clean.band_low", rc["band"] == "LOW", rc["band"])

print("== 5. 双大脑去重 ==")
from patchpilot.agent import _dedupe  # noqa: E402
from patchpilot.models import Finding  # noqa: E402
dup = _dedupe([
    Finding("HIGH", "BARE_EXCEPT", "裸 except", 5, "offline msg", "s", source="offline"),
    Finding("HIGH", "bare_except", "裸 except", 5, "nemotron longer message here", "s2", source="nemotron"),
])
check("dedupe.count==1", len(dup) == 1, len(dup))
check("dedupe.merged_source", "offline" in dup[0].source and "nemotron" in dup[0].source, dup[0].source)
check("dedupe.kept_richer_msg", "nemotron" in dup[0].message, dup[0].message)

print("== 6. 回执渲染 ==")
html = html_receipt(r)
check("receipt.html_ok", "<!DOCTYPE html>" in html and "PatchPilot" in html)
check("receipt.html_has_findings", "BARE_EXCEPT" in html)
check("receipt.html_has_patch", "except Exception:" in html)
txt = text_receipt(r)
check("receipt.text_ok", "PatchPilot" in txt and "风险评分" in txt)

print("== 6b. 英文回执（i18n） ==")
from patchpilot import i18n  # noqa: E402
from patchpilot.lint import _LINE_RULES  # noqa: E402

with open(os.path.join(_HERE, "examples", "bad_code_en.py"),
          encoding="utf-8") as f:
    BAD_EN = f.read()
r_en = dp.review(BAD_EN, use_llm=False)
txt_en = text_receipt(r_en, lang="en")
check("i18n.en_has_english_rule", "Hardcoded secret" in txt_en
      and "Bare except" in txt_en, txt_en[:120])
check("i18n.en_has_english_ui", "Risk score" in txt_en
      and "Patch suggestions" in txt_en)
check("i18n.en_no_fullwidth", not any(c in txt_en for c in "；，。：（）"))
check("i18n.en_explains_highs", "Fix the high-severity findings first" in txt_en)
check("i18n.en_patch_rationale_en", "Compare with None using is / is not."
      in txt_en or "Narrow the bare except to Exception." in txt_en)
check("i18n.zh_default_unchanged", "硬编码密钥" in txt and "风险评分" in txt)
ALL_CODES = [c for c, *_ in _LINE_RULES] + ["LONG_LINE", "SWALLOWED_EXCEPT"]
missing = [c for c in ALL_CODES if i18n.rule_en(c) is None]
check("i18n.all_rules_translated", not missing, str(missing))
check("i18n.patch_map_complete",
      i18n.PATCH_EN.get("None 比较改用 is/is not。") == "Compare with None using is / is not.")

print("== 7. 空输入 ==")
re_ = dp.review("   ")
check("empty.not_ok", re_["ok"] is False)

print("== 8. Tavily 证据检索层 ==")
from patchpilot.research import (  # noqa: E402
    CODE_INTENT, EvidenceGate, ResearchLayer, TavilyClient, TavilyError,
    domain_of, fixture_evidence, plan_queries, tier_of, _norm,
)

check("tavily.tier1_domain", tier_of("https://cwe.mitre.org/data/definitions/95.html") == 3,
      tier_of("https://cwe.mitre.org/data/definitions/95.html"))
check("tavily.tier1_docs_python", tier_of("https://docs.python.org/3/") == 3)
check("tavily.tier1_readthedocs", tier_of("https://bandit.readthedocs.io/en/latest/") == 3)
check("tavily.tier2_stackoverflow", tier_of("https://stackoverflow.com/a/1") == 1)
check("tavily.tier3_unknown", tier_of("https://example.org/post") == 0)
check("tavily.blocked_farm", tier_of("https://seowebsite.example.com/eval") == -1)
check("tavily.www_stripped", domain_of("https://WWW.Docs.Python.org:443/3/") == "docs.python.org",
      domain_of("https://WWW.Docs.Python.org:443/3/"))

check("tavily.norm_drops_utm",
      _norm("https://a.org/x?utm_source=s&id=2") == _norm("https://a.org/x?id=2"),
      f"{_norm('https://a.org/x?utm_source=s&id=2')} vs {_norm('https://a.org/x?id=2')}")


class _FakeFinding:
    def __init__(self, code, severity="HIGH", rule="r"):
        self.code = code
        self.severity = severity
        self.rule = rule


p_eval = plan_queries(_FakeFinding("EVAL_EXEC"))
check("tavily.plan_eval_is_cve", p_eval is not None and p_eval["intent"] == "cve_advisory",
      p_eval)
check("tavily.plan_eval_topic_news", p_eval["params"]["topic"] == "news")
check("tavily.plan_eval_domain_filter",
      p_eval["params"]["include_domains_mode"] == "filter"
      and "cwe.mitre.org" in p_eval["params"]["include_domains"])
check("tavily.plan_todo_none", plan_queries(_FakeFinding("TODO_FIXME")) is None,
      "TODO/FIXME 不该消耗检索预算")

_RESULTS = [
    {"title": "CWE-95 Eval Injection", "url": "https://cwe.mitre.org/data/definitions/95.html",
     "content": "The product receives input and passes it to eval injection vulnerability CWE-95",
     "score": 0.9},
    {"title": "SEO junk", "url": "https://seowebsite.example.com/eval",
     "content": "eval injection vulnerability"},
    {"title": "Random blog", "url": "https://example.org/post",
     "content": "nothing relevant at all"},
    {"title": "Built-in Functions", "url": "https://docs.python.org/3/library/functions.html",
     "content": "python documentation eval vulnerability"},
    {"title": "Dup with utm",
     "url": "https://cwe.mitre.org/data/definitions/95.html?utm_source=x",
     "content": "eval injection vulnerability"},
]
_MUST = ("cve", "vulnerab", "exploit", "advisory", "security", "injection")
admitted, rejected = EvidenceGate().admit(_RESULTS, _MUST, set())
check("tavily.gate_admitted_two", len(admitted) == 2, [a["url"] for a in admitted])
check("tavily.gate_tier_sorted", [a["domain"] for a in admitted] ==
      ["cwe.mitre.org", "docs.python.org"], [a["domain"] for a in admitted])
whys = " ".join(r["why"] for r in rejected)
check("tavily.gate_rejects_farm", "blocked domain" in whys, whys)
check("tavily.gate_rejects_low_tier", "below minimum" in whys, whys)
check("tavily.gate_rejects_dup", "duplicate url" in whys, whys)
check("tavily.gate_rejects_no_keyword",
      EvidenceGate().admit([{"url": "https://docs.python.org/3/", "title": "t",
                             "content": "zzz"}], _MUST, set())[0] == [])


class _FakeClient:
    """假 Tavily：不联网，验证 enrich 的完整编排。"""

    def __init__(self, results, body):
        self._results = results
        self._body = body
        self.calls = {}
        self.credits = 0.0
        self.errors = []

    def search(self, query, **params):
        self.calls["/search"] = self.calls.get("/search", 0) + 1
        self.credits += 2
        return {"results": self._results, "usage": {"credits": 2}}

    def extract(self, urls, query="", **params):
        """按 URL 返回对应正文（模拟真实 extract 行为）。"""
        self.calls["/extract"] = self.calls.get("/extract", 0) + 1
        hit = [r for r in self._results if r.get("url") == urls[0]]
        body = hit[0]["content"].lower() if hit else self._body
        return {"results": [{"url": urls[0], "raw_content": body + " extra body text"}]}


fake = _FakeClient(_RESULTS, _RESULTS[0]["content"].lower() + " extra body text")
layer = ResearchLayer(client=fake, max_search=4, max_extract=2)
findings = [_FakeFinding("EVAL_EXEC"), _FakeFinding("HARDCODED_SECRET"),
            _FakeFinding("TODO_FIXME")]
bundle = layer.enrich(findings)
check("tavily.enrich_mode", bundle["mode"] == "tavily", bundle["mode"])
check("tavily.enrich_admitted", bundle["gate"]["admitted"] > 0, bundle["gate"])
check("tavily.enrich_considered", bundle["gate"]["considered"] == 10, bundle["gate"])
check("tavily.enrich_search_calls", bundle["calls"].get("/search") == 2, bundle["calls"])
check("tavily.enrich_extract_capped", bundle["calls"].get("/extract") == 2, bundle["calls"])
check("tavily.enrich_credits", bundle["credits"] == 4.0, bundle["credits"])
check("tavily.enrich_quote_verified",
      all(e.get("quote_verified") for e in bundle["evidence"]),
      [(e.get("quote_matched"), e.get("quote_probes")) for e in bundle["evidence"]])
check("tavily.enrich_has_for", all("for" in e for e in bundle["evidence"]))
check("tavily.enrich_not_degraded", bundle["degraded"] is False, bundle.get("reason"))

# 预算耗尽：max_search=1 时只查一次
fake2 = _FakeClient(_RESULTS, _RESULTS[0]["content"].lower())
b2 = ResearchLayer(client=fake2, max_search=1, max_extract=0).enrich(findings)
check("tavily.budget_search_cap", b2["calls"].get("/search") == 1, b2["calls"])
check("tavily.budget_no_extract", b2["calls"].get("/extract") is None, b2["calls"])
check("tavily.budget_quote_unverified",
      all(not e.get("quote_verified") for e in b2["evidence"]))

# 检索全灭：一条都不该崩，且要留降级原因
fake3 = _FakeClient([{"url": "https://example.org/x", "title": "t", "content": "zzz"}],
                    "")
b3 = ResearchLayer(client=fake3, max_search=2, max_extract=1).enrich(findings)
check("tavily.empty_degraded", b3["degraded"] is True and b3["evidence"] == [], b3)

# 网络失败：TavilyError 必须被吞掉，不能拖垮审查
class _BoomClient(_FakeClient):
    def search(self, query, **params):
        raise TavilyError("boom")


b4 = ResearchLayer(client=_BoomClient([], ""), max_search=2).enrich(findings)
check("tavily.error_degraded", b4["degraded"] is True and "boom" in (b4["reason"] or ""), b4)
check("tavily.error_no_evidence", b4["evidence"] == [])

# 真实客户端的 HTTP 错误路径（打到一个必挂的地址）
bad = TavilyClient("tvly-test", base="http://127.0.0.1:9", timeout=2)
try:
    bad.search("x")
    check("tavily.http_error_raises", False, "should have raised")
except TavilyError:
    check("tavily.http_error_raises", True)

# 离线 fixture 通路
off_layer = ResearchLayer.from_env(offline=True)
check("tavily.offline_mode", off_layer.mode == "offline-fixture", off_layer.mode)
check("tavily.env_offline_mode", ResearchLayer.from_env(offline=True).client is None)
check("tavily.fixture_nonempty", len(fixture_evidence(findings)) > 0)
check("tavily.fixture_flagged", all(e.get("fixture") for e in fixture_evidence(findings)))

dp_ev = PatchPilot(offline_evidence=True)
r_ev = dp_ev.review(BAD, use_llm=False, use_search=True)
check("tavily.e2e_ok", r_ev["ok"] is True)
check("tavily.e2e_mode", r_ev["evidence"]["mode"] == "offline-fixture", r_ev["evidence"])
check("tavily.e2e_refs_nonempty", len(r_ev["references"]) > 0, len(r_ev["references"]))
check("tavily.e2e_reason_present", bool(r_ev["evidence"].get("reason")))
ev_html = html_receipt(r_ev)
check("tavily.e2e_html_section", "Tavily 证据" in ev_html)
check("tavily.e2e_html_gate", "证据闸门" in ev_html)
check("tavily.e2e_text", "Tavily 证据（offline-fixture）" in text_receipt(r_ev))

# 不开检索时不该有任何网络副作用
r_off = PatchPilot(offline_evidence=True).review(BAD, use_llm=False, use_search=False)
check("tavily.no_search_no_evidence", r_off["references"] == [] and r_off["evidence"] == {})

print("== 9. Nebius 通路（有 Key 才测，无则跳过） ==")
if os.environ.get("NEBIUS_API_KEY"):
    dp2 = PatchPilot()
    check("nebius.reviewer_present", dp2.reviewer is not None)
    r2 = dp2.review(BAD)
    check("nebius.review_ok", r2["ok"] is True)
    print(f"  [info] nemotron_used={r2['nemotron_used']} findings={len(r2['findings'])}")
else:
    print("  [SKIP] 未设置 NEBIUS_API_KEY，跳过 Nemotron 实网测试")

print("\n" + "=" * 48)
print(f"结果：{_passed} 通过 / {_failed} 失败")
print(f"RESULT: {_passed} passed, {_failed} failed")
print("=" * 48)
sys.exit(1 if _failed else 0)
