"""PatchPilot 离线 Linter 大脑（零依赖，确定性，可复现）。

一套真实可用的 Python 静态检查规则：裸 except、eval/exec、硬编码密钥、被吞掉的异常、
== None、可变默认参数、import *、调试 print、TODO、超长行、== True/False、type()==。
它是"永远可用"的兜底大脑：无 Nebius Key 时也能产出有价值的审查，也是确定性自测的基础。
每条发现都带 evidence（触发匹配的原始行），可解释、可核对。
"""

from __future__ import annotations

import re
from typing import List

from .models import Finding, Patch

# (code, severity, rule, compiled_regex, message, suggestion)
_LINE_RULES = [
    ("BARE_EXCEPT", "HIGH", "裸 except",
     re.compile(r"except\s*:"),
     "裸 except 会吞掉所有异常（包括 KeyboardInterrupt/SystemExit），隐藏真实错误。",
     "改为捕获具体异常类型，如 except ValueError:"),
    ("EVAL_EXEC", "HIGH", "eval/exec 注入风险",
     re.compile(r"(?<!\w)(eval|exec)\s*\("),
     "eval/exec 可执行任意代码，是代码注入的高危入口。",
     "避免动态执行；用 ast.literal_eval 解析字面量，或用显式分发替代。"),
    ("HARDCODED_SECRET", "HIGH", "硬编码密钥",
     re.compile(r"(?i)\b(password|passwd|pwd|api_key|apikey|secret|token|access_key|private_key)\b"
                r"\s*=\s*[\"'][^\"'\s]{4,}[\"']"),
     "疑似把密钥/令牌硬编码进源码，会随仓库泄露。",
     "改为从环境变量或密钥管理服务读取，并轮换已泄露的密钥。"),
    ("EQ_NONE", "CAUTION", "用 == 比较 None",
     re.compile(r"[!=]=\s*None"),
     "应使用 is / is not 与 None 比较，== 依赖对象的 __eq__ 实现，可能被误导。",
     "把 == None 改为 is None，!= None 改为 is not None。"),
    ("EQ_BOOL", "CAUTION", "用 == 比较布尔",
     re.compile(r"==\s*(True|False)\b"),
     "直接判断真值即可，无需与 True/False 比较。",
     "把 == True 改为直接判断该表达式，== False 用 not。"),
    ("TYPE_EQ", "CAUTION", "用 type()== 判型",
     re.compile(r"type\s*\(\s*[\w.]+\s*\)\s*=="),
     "type()== 不考虑继承，应用 isinstance。",
     "改用 isinstance(obj, ClassName)。"),
    ("MUTABLE_DEFAULT", "CAUTION", "可变默认参数",
     re.compile(r"def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|set\(\))"),
     "可变对象作默认参数会在多次调用间共享状态，是经典陷阱。",
     "默认值设为 None，函数体内再初始化为 [] / {} / set()。"),
    ("IMPORT_STAR", "CAUTION", "import *",
     re.compile(r"from\s+[\w.]+\s+import\s+\*"),
     "import * 会污染命名空间，掩盖来源、易冲突。",
     "显式导入所需名字，或 import module 后 module.name 使用。"),
    ("PRINT_DEBUG", "INFO", "调试 print 残留",
     re.compile(r"(?<!\w)print\s*\("),
     "生产代码里的 print 会污染输出、泄露信息，应改用日志。",
     "改用 logging 模块并按级别输出。"),
    ("TODO_FIXME", "INFO", "TODO/FIXME 标记",
     re.compile(r"#\s*(TODO|FIXME|XXX|HACK)\b"),
     "存在未完成的 TODO/FIXME 标记。",
     "登记到 Issue 跟踪，或在本轮清理。"),
]

_LONG_LINE_MAX = 100


class OfflineLinter:
    """确定性 Python 静态检查器。"""

    name = "offline"

    def lint(self, code: str) -> List[Finding]:
        findings: List[Finding] = []
        lines = code.splitlines()

        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                # 注释行只查 TODO 标记
                for code_id, sev, rule, rx, msg, sug in _LINE_RULES:
                    if code_id == "TODO_FIXME":
                        m = rx.search(line)
                        if m:
                            findings.append(Finding(sev, code_id, rule, i, msg, sug,
                                                    evidence=m.group(0), source=self.name))
                continue
            for code_id, sev, rule, rx, msg, sug in _LINE_RULES:
                if code_id == "TODO_FIXME":
                    continue
                m = rx.search(line)
                if m:
                    findings.append(Finding(sev, code_id, rule, i, msg, sug,
                                            evidence=line.strip()[:120], source=self.name))
            if len(line) > _LONG_LINE_MAX:
                findings.append(Finding("INFO", "LONG_LINE", "超长行", i,
                                        f"行长度 {len(line)} > {_LONG_LINE_MAX}，影响可读性。",
                                        "拆分长行或提取中间变量。",
                                        evidence=line.strip()[:60] + "…", source=self.name))

        # 多行规则：被 pass 吞掉的 except（next 行以 pass 开头，允许尾注注释）
        for i in range(len(lines) - 1):
            cur = lines[i].strip()
            nxt = lines[i + 1].strip()
            if re.match(r"except\b", cur) and re.match(r"pass\b", nxt):
                findings.append(Finding("CAUTION", "SWALLOWED_EXCEPT", "异常被静默吞掉", i + 1,
                                        "except 后直接 pass 会静默吞掉异常，问题难以排查。",
                                        "至少记录日志，或按类型处理/向上抛出。",
                                        evidence=f"{cur} / {nxt}", source=self.name))

        return findings

    def suggest_patches(self, code: str, findings: List[Finding]) -> List[Patch]:
        """对可机械修复的问题给出 before/after 补丁建议（确定性）。"""
        lines = code.splitlines()
        patches: List[Patch] = []
        for f in findings:
            if not (1 <= f.line <= len(lines)):
                continue
            before = lines[f.line - 1]
            after = None
            rationale = ""
            if f.code == "EQ_NONE":
                after = before.replace("== None", "is None").replace("!= None", "is not None")
                rationale = "None 比较改用 is/is not。"
            elif f.code == "EQ_BOOL":
                after = re.sub(r"==\s*True\b", "", before).replace("== False", "")
                after = after.rstrip()
                rationale = "去掉与 True/False 的显式比较。"
            elif f.code == "BARE_EXCEPT":
                after = before.replace("except:", "except Exception:")
                rationale = "裸 except 收窄为 Exception。"
            if after and after != before:
                patches.append(Patch(f.line, before, after, rationale, source=self.name))
        return patches
