"""PatchPilot LLM 大脑：Nebius Token Factory + NVIDIA Nemotron 深度代码审查。

Nebius Token Factory 是 OpenAI 兼容推理服务，base_url 指向它即可用 NVIDIA 开源模型
（Nemotron）。无 Key 时上层回落到离线 Linter（功能完整、可演示）。
另含可选的 Tavily 检索增强（Best Use of Tavily 赛道加分项），无 Key 自动跳过。
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import List, Optional

from .models import Finding

_NEBIUS_DEFAULT_BASE = "https://api.tokenfactory.nebius.com/v1/"
_NEBIUS_DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"

_SYSTEM = (
    "你是资深代码审查引擎。分析给定的 Python 代码，只输出 JSON，勿解释。"
    "JSON 结构：{\"findings\":[{\"severity\":\"HIGH|CAUTION|INFO\",\"code\":\"短代号\","
    "\"line\":行号,\"message\":\"问题\",\"suggestion\":\"建议\"}],"
    "\"patches\":[{\"line\":行号,\"after\":\"修改后的整行\",\"rationale\":\"理由\"}]}。"
    "聚焦真实的 bug、安全、正确性、性能问题；不要编造，没有问题就返回空数组。"
)


class NemotronReviewer:
    """跑在 Nebius Token Factory 上的 NVIDIA Nemotron 深度审查器。"""

    name = "nemotron"

    def __init__(self, base_url: str, api_key: str, model: str = _NEBIUS_DEFAULT_MODEL,
                 timeout: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def review(self, code: str) -> List[Finding]:
        findings, _ = self.analyze(code)
        return findings

    def analyze(self, code: str):
        """一次调用同时返回 (findings, patches)，避免双倍计费。"""
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": code[:12000]},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        data = json.loads(content[content.find("{"):content.rfind("}") + 1])
        findings: List[Finding] = []
        for f in data.get("findings", []):
            try:
                findings.append(Finding(
                    severity=str(f.get("severity", "INFO")).upper(),
                    code=str(f.get("code", "NEMOTRON")),
                    rule="Nemotron 深度审查",
                    line=int(f.get("line", 0) or 0),
                    message=str(f.get("message", "")),
                    suggestion=str(f.get("suggestion", "")),
                    evidence="", source=self.name,
                ))
            except (TypeError, ValueError):
                continue
        patches = data.get("patches", [])
        return findings, patches


class TavilySearch:
    """可选的 Tavily 检索增强：为发现的问题补充"当前最佳实践"参考。"""

    name = "tavily"

    def __init__(self, api_key: str, base: str = "https://api.tavily.com",
                 timeout: int = 30) -> None:
        self.api_key = api_key
        self.base = base.rstrip("/")
        self.timeout = timeout

    def search(self, query: str, max_results: int = 3) -> List[dict]:
        body = json.dumps({
            "api_key": self.api_key, "query": query, "max_results": max_results,
            "search_depth": "basic",
        }).encode()
        req = urllib.request.Request(f"{self.base}/search", data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode())
        return [{"title": r.get("title", ""), "url": r.get("url", "")}
                for r in data.get("results", [])[:max_results]]


def get_reviewer() -> Optional[NemotronReviewer]:
    """有 NEBIUS_API_KEY 就走 Nemotron，否则 None（上层用离线 Linter）。"""
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        return None
    base = os.environ.get("NEBIUS_BASE", _NEBIUS_DEFAULT_BASE)
    model = os.environ.get("NEBIUS_MODEL", _NEBIUS_DEFAULT_MODEL)
    try:
        return NemotronReviewer(base, key, model)
    except Exception:
        return None


def get_search() -> Optional[TavilySearch]:
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        return None
    try:
        return TavilySearch(key)
    except Exception:
        return None
