"""PatchPilot 智能体：跑在 Nebius + NVIDIA Nemotron 上的代码审查/自动修复 agent。

处理环（每步可解释）：
  PERCEIVE  识别语言、统计行数
  LINT      离线 Linter（确定性兜底大脑）→ findings + 机械补丁
  REASON    Nemotron 深度审查（有 Key 时）→ 语义 findings + 补丁；失败自动回落离线
  RETRIEVE  可选 Tavily 检索：为高危问题补充"当前最佳实践"参考
  PLAN      合并双大脑发现（去重）+ 汇总补丁
  EXPLAIN   大白话结论
  RECEIPT   结构化回执（含证据）

无 NEBIUS_API_KEY 时仅用离线 Linter，功能完整、可演示；有 Key 即升级为 Nemotron 深度审查。
"""

from __future__ import annotations

from typing import Optional

from .lint import OfflineLinter
from .llm import get_reviewer, get_search
from .models import Finding, Patch, Review


def _dedupe(findings: list) -> list:
    """按 (code 小写, line) 去重；同一处被双大脑命中则合并来源标注。"""
    seen: dict = {}
    order: list = []
    for f in findings:
        key = (f.code.lower(), f.line)
        if key in seen:
            prev = seen[key]
            if f.source not in prev.source:
                prev.source = f"{prev.source}+{f.source}"
            # 保留信息更丰富的 message（更长者）
            if len(f.message) > len(prev.message):
                prev.message = f.message
                prev.suggestion = f.suggestion or prev.suggestion
            continue
        seen[key] = f
        order.append(key)
    return [seen[k] for k in order]


class PatchPilot:
    def __init__(self, reviewer=None, search=None) -> None:
        self.linter = OfflineLinter()
        self.reviewer = reviewer if reviewer is not None else get_reviewer()
        self.search = search if search is not None else get_search()

    @property
    def brain(self) -> str:
        return "offline+nemotron" if self.reviewer else "offline"

    def review(self, code: str, use_llm: bool = True, use_search: bool = False) -> dict:
        if not code.strip():
            return {"ok": False, "error": "输入为空，无代码可审查。"}

        # PERCEIVE
        lines = code.splitlines()
        language = "python"

        # LINT（离线兜底，永远执行）
        findings = self.linter.lint(code)
        patches = self.linter.suggest_patches(code, findings)
        nemotron_used = False

        # REASON（Nemotron 深度审查）
        if use_llm and self.reviewer is not None:
            try:
                n_find, n_patch_raw = self.reviewer.analyze(code)
                findings.extend(n_find)
                for p in n_patch_raw:
                    try:
                        patches.append(Patch(
                            line=int(p.get("line", 0) or 0),
                            before=(lines[int(p.get("line", 1)) - 1] if 1 <= int(p.get("line", 1)) <= len(lines) else ""),
                            after=str(p.get("after", "")),
                            rationale=str(p.get("rationale", "")),
                            source="nemotron",
                        ))
                    except (TypeError, ValueError):
                        continue
                nemotron_used = True
            except Exception:
                nemotron_used = False  # 优雅回落，不崩溃

        # RETRIEVE（可选 Tavily）
        references = []
        if use_search and self.search is not None:
            try:
                highs = [f for f in findings if f.severity == "HIGH"][:2]
                for f in highs:
                    refs = self.search.search(f"{f.rule} {f.message[:60]} best practice")
                    for r in refs:
                        references.append({"for": f.code, **r})
            except Exception:
                pass

        # PLAN（合并去重）
        merged = _dedupe(findings)

        # 评分
        highs = sum(1 for f in merged if f.severity == "HIGH")
        cautions = sum(1 for f in merged if f.severity == "CAUTION")
        infos = sum(1 for f in merged if f.severity == "INFO")
        score = min(100, highs * 30 + cautions * 10 + infos * 2)
        band = "HIGH" if score >= 30 else ("MEDIUM" if score >= 10 else "LOW")

        if not merged:
            summary = f"审查 {len(lines)} 行 {language} 代码，未发现明显问题。"
        else:
            summary = (f"审查 {len(lines)} 行 {language} 代码，发现 {highs} 个高危、"
                       f"{cautions} 个待留意、{infos} 个提示，风险等级 {band}。")

        explain = self._explain(merged, patches, nemotron_used, references)

        return {
            "ok": True, "language": language, "lines": len(lines),
            "brain": self.brain, "nemotron_used": nemotron_used,
            "score": score, "band": band, "summary": summary,
            "findings": [self._f_dict(f) for f in merged],
            "patches": [self._p_dict(p) for p in patches],
            "references": references,
            "explain": explain,
        }

    @staticmethod
    def _f_dict(f: Finding) -> dict:
        return {"severity": f.severity, "code": f.code, "rule": f.rule, "line": f.line,
                "message": f.message, "suggestion": f.suggestion, "evidence": f.evidence,
                "source": f.source}

    @staticmethod
    def _p_dict(p: Patch) -> dict:
        return {"line": p.line, "before": p.before, "after": p.after,
                "rationale": p.rationale, "source": p.source}

    @staticmethod
    def _explain(findings, patches, nemotron_used, references) -> str:
        lines = []
        highs = [f for f in findings if f.severity == "HIGH"]
        if highs:
            lines.append("⚠️ 建议优先处理高危问题：")
            for f in highs:
                loc = f"L{f.line}" if f.line else "?"
                lines.append(f"  - [{f.code}] {loc}：{f.message}")
        else:
            lines.append("✅ 未发现高危问题。")
        if patches:
            lines.append(f"🔧 已生成 {len(patches)} 条可执行补丁建议（见 patches）。")
        if nemotron_used:
            lines.append("🧠 本轮启用了 NVIDIA Nemotron（经 Nebius Token Factory）深度审查。")
        else:
            lines.append("ℹ️ 当前为离线 Linter 模式；配置 NEBIUS_API_KEY 即可启用 Nemotron 深度审查。")
        if references:
            lines.append(f"🔎 已附 {len(references)} 条最佳实践参考（Tavily）。")
        return "\n".join(lines)
