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

print("== 7. 空输入 ==")
re_ = dp.review("   ")
check("empty.not_ok", re_["ok"] is False)

print("== 8. Nebius 通路（有 Key 才测，无则跳过） ==")
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
print("=" * 48)
sys.exit(1 if _failed else 0)
