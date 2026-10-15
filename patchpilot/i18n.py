# -*- coding: utf-8 -*-
"""PatchPilot bilingual layer (zh default / en).

Render-time translation: the linter keeps emitting Chinese rule metadata,
and this module maps each rule code plus the UI strings to English so the
same review can be printed for an international audience without touching
the detection logic.
"""
from __future__ import annotations

# code -> (rule_en, message_en, suggestion_en)
RULE_EN = {
    "BARE_EXCEPT": (
        "Bare except",
        "A bare except swallows every exception (including "
        "KeyboardInterrupt/SystemExit) and hides the real error.",
        "Catch specific exception types, e.g. except ValueError:",
    ),
    "EVAL_EXEC": (
        "eval/exec injection risk",
        "eval/exec can run arbitrary code - a high-risk code-injection entry point.",
        "Avoid dynamic execution; parse literals with ast.literal_eval, "
        "or use explicit dispatch instead.",
    ),
    "HARDCODED_SECRET": (
        "Hardcoded secret",
        "A secret or token appears to be hardcoded in source and will leak "
        "with the repository.",
        "Read it from an environment variable or a secrets manager, and "
        "rotate the leaked credential.",
    ),
    "EQ_NONE": (
        "Comparing to None with ==",
        "Use is / is not with None; == relies on the object's __eq__ "
        "implementation and can be misled.",
        "Change == None to is None, != None to is not None.",
    ),
    "EQ_BOOL": (
        "Comparing to a boolean with ==",
        "Test the truth value directly; there is no need to compare with "
        "True/False.",
        "Drop == True and test the expression directly; use not for == False.",
    ),
    "TYPE_EQ": (
        "Type check with type()==",
        "type()== ignores inheritance; use isinstance.",
        "Use isinstance(obj, ClassName) instead.",
    ),
    "MUTABLE_DEFAULT": (
        "Mutable default argument",
        "A mutable object as a default argument is shared between calls - "
        "the classic Python trap.",
        "Default to None and initialise [] / {} / set() inside the function body.",
    ),
    "IMPORT_STAR": (
        "import *",
        "import * pollutes the namespace, hides origins and invites collisions.",
        "Import the names you need explicitly, or import module and use "
        "module.name.",
    ),
    "PRINT_DEBUG": (
        "Leftover debug print",
        "print in production code pollutes output and can leak information; "
        "use logging instead.",
        "Switch to the logging module and emit by level.",
    ),
    "TODO_FIXME": (
        "TODO/FIXME marker",
        "An unfinished TODO/FIXME marker is present.",
        "Track it as an issue, or clean it up in this pass.",
    ),
    "LONG_LINE": (
        "Overlong line",
        "The line exceeds 100 characters, hurting readability.",
        "Split the line or extract an intermediate variable.",
    ),
    "SWALLOWED_EXCEPT": (
        "Silently swallowed exception",
        "A pass directly after except swallows the exception, making "
        "problems hard to trace.",
        "At least log it, or handle by type / re-raise.",
    ),
}

# patch rationale (zh) -> en, keyed by the exact Chinese string
PATCH_EN = {
    "None 比较改用 is/is not。": "Compare with None using is / is not.",
    "去掉与 True/False 的显式比较。": "Drop the explicit True/False comparison.",
    "裸 except 收窄为 Exception。": "Narrow the bare except to Exception.",
}

# severity bands stay as-is (HIGH / CAUTION / INFO are language-neutral)

UI_EN = {
    "title": "PatchPilot · code review receipt",
    "brain_line": "Brain: {brain}    Language: {language}    Lines: {lines}",
    "score_line": "Risk score: {score}/100    Band: {band}",
    "summary_clean": "Reviewed {lines} lines of {language} code - no obvious issues found.",
    "summary_findings": ("Reviewed {lines} lines of {language} code - "
                         "{highs} high, {cautions} caution, {infos} info; "
                         "risk band {band}."),
    "patches_header": "Patch suggestions:",
    "evidence_header": "Tavily evidence ({mode}):",
    "gate_line": ("Gate: {considered} considered -> {admitted} admitted"
                  " · endpoints {calls} · credits {credits}"),
    "tier": {0: "unrated", 1: "low", 2: "medium", 3: "high"},
    "explain_highs": "Fix the high-severity findings first:",
    "explain_clean": "No high-severity findings.",
    "explain_patches": "{n} executable patch suggestions generated (see patches).",
    "explain_nemotron": ("NVIDIA Nemotron (via Nebius Token Factory) deep "
                         "review was enabled this round."),
    "explain_offline": ("Offline linter mode; set NEBIUS_API_KEY to enable "
                        "Nemotron deep review."),
    "explain_tavily": "Tavily evidence: {n} refs ({mode}, {verified} verified against source text).",
    "unprocessable": "cannot process",
    "evidence_written": "\nEvidence bundle written to: {path}",
    "html_written": "\nHTML report written to: {path}",
}

LANGS = ("zh", "en")


def t(lang: str, key: str, **kw) -> str:
    """Look up an English UI string and format it (zh lives at call sites)."""
    return UI_EN[key].format(**kw)


def rule_en(code: str):
    """Return (rule, message, suggestion) in English, or None if unknown."""
    return RULE_EN.get(code)
