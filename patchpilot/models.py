"""PatchPilot 数据模型（零依赖，纯标准库）。

一条代码审查发现 + 一个补丁建议 + 一份审查报告。
离线 Linter 与 Nebius/NVIDIA Nemotron 深度审查产出同一份 Finding，上层无需关心来源。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Finding:
    severity: str            # HIGH / CAUTION / INFO
    code: str                # 规则/问题代号，如 BARE_EXCEPT
    rule: str                # 人类可读规则名
    line: int                # 行号（0 表示无法定位）
    message: str
    suggestion: str
    evidence: str = ""       # 触发匹配的原始代码片段（可解释性）
    source: str = "offline"  # offline | nemotron


@dataclass
class Patch:
    line: int
    before: str
    after: str
    rationale: str
    source: str = "offline"


@dataclass
class Review:
    language: str = "python"
    findings: list = field(default_factory=list)
    patches: list = field(default_factory=list)
    score: int = 0
    band: str = "LOW"
    summary: str = ""
    brain: str = "offline"
    lines_scanned: int = 0
