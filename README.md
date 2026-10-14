# PatchPilot 🩹 — An agentic code reviewer running on Nebius + NVIDIA Nemotron

**Paste code, get an AI review in seconds.** PatchPilot is an *agentic* code-review and
auto-fix tool built for the **Nebius × NVIDIA Global AI Hackathon**. It runs a real
multi-step agent loop on **Nebius Token Factory** with **NVIDIA Nemotron**, and degrades
gracefully to a deterministic offline linter when no API key is present — so it demos
fully out of the box.

- ⚡ **Runs on Nebius Token Factory** (OpenAI-compatible) + **NVIDIA Nemotron**
  (`nvidia/nemotron-3-super-120b-a12b`) — the model does the deep semantic review.
- 🛡️ **Dual brain:** a deterministic offline linter (12 real rules, always available) +
  Nemotron deep review. No key → still fully functional.
- 🔧 **Auto-fix:** emits before/after patch diffs for mechanically-fixable issues.
- 🔎 **Explainable:** every finding carries a line number + the evidence line; optional
  **Tavily** search enriches high-severity findings with current best-practice references.
- 🧪 **Self-test:** `python eval.py` → **37/37 assertions pass**, zero dependencies.

---

## The agent loop

```
PERCEIVE  detect language, count lines
LINT      deterministic offline linter (fallback brain) → findings + mechanical patches
REASON    NVIDIA Nemotron via Nebius Token Factory → semantic findings + patches
          (fails gracefully back to offline; never crashes the demo)
RETRIEVE  optional Tavily search → best-practice references for high-severity findings
PLAN      merge + de-duplicate both brains' findings
EXPLAIN   plain-language conclusion
RECEIPT   structured report (text / HTML) with evidence
```

---

## Quick start

No `pip install` anything — pure Python 3.8+ standard library.

```bash
# Review the bundled "bad code" sample (offline mode, no key needed)
python -m patchpilot.cli examples/bad_code.py

# HTML report
python -m patchpilot.cli examples/bad_code.py --html report.html

# Offline self-test suite
python eval.py

# Web console
python server.py          # → http://localhost:8000
```

Expected (offline) output for the sample:

```
风险评分：100/100    等级：HIGH
审查 19 行 python 代码，发现 3 个高危、6 个待留意、3 个提示，风险等级 HIGH。
🔴 [HIGH] 硬编码密钥（HARDCODED_SECRET）L6 · offline
    📎 password = "SuperSecret123!"
🟡 [CAUTION] 可变默认参数（MUTABLE_DEFAULT）L5
    👉 默认值设为 None，函数体内再初始化为 [] / {} / set()。
```

## Enable NVIDIA Nemotron (deep review)

```bash
export NEBIUS_API_KEY=...                       # Nebius account → free credits to start
export NEBIUS_BASE=https://api.tokenfactory.nebius.com/v1/
export NEBIUS_MODEL=nvidia/nemotron-3-super-120b-a12b
python -m patchpilot.cli examples/bad_code.py   # now uses Nemotron deep review
```

Optional Tavily enrichment (Best Use of Tavily):

```bash
export TAVILY_API_KEY=...
python -m patchpilot.cli examples/bad_code.py --search
```

With a key present, findings from both brains are merged and de-duplicated (same
`code`+`line` → one finding, sources combined). Without a key, the offline linter alone
produces a complete, useful review.

---

## What the offline linter catches (12 rules)

| Severity | Rule | Catches |
|---|---|---|
| 🔴 HIGH | BARE_EXCEPT | `except:` swallowing everything |
| 🔴 HIGH | EVAL_EXEC | `eval()` / `exec()` injection risk |
| 🔴 HIGH | HARDCODED_SECRET | secrets/tokens hardcoded in source |
| 🟡 CAUTION | SWALLOWED_EXCEPT | `except …: pass` silently |
| 🟡 CAUTION | EQ_NONE | `== None` (should be `is None`) |
| 🟡 CAUTION | EQ_BOOL | `== True/False` |
| 🟡 CAUTION | TYPE_EQ | `type(x)==` (should be `isinstance`) |
| 🟡 CAUTION | MUTABLE_DEFAULT | `def f(x=[])` shared-state trap |
| 🟡 CAUTION | IMPORT_STAR | `from x import *` |
| 🔵 INFO | PRINT_DEBUG | leftover debug `print()` |
| 🔵 INFO | TODO_FIXME | TODO/FIXME markers |
| 🔵 INFO | LONG_LINE | lines > 100 chars |

Mechanical patches are auto-generated for BARE_EXCEPT, EQ_NONE, and EQ_BOOL.

---

## As a library

```python
from patchpilot import PatchPilot

pp = PatchPilot()                      # auto-detects NEBIUS_API_KEY / TAVILY_API_KEY
result = pp.review(open("code.py").read(), use_llm=True, use_search=False)
print(result["score"], result["band"])
for f in result["findings"]:
    print(f["severity"], f["code"], "L%s" % f["line"], f["message"])
for p in result["patches"]:
    print("patch L%s: %s -> %s" % (p["line"], p["before"], p["after"]))
```

---

## Configuration

| Env var | Purpose | Default if unset |
|---|---|---|
| `NEBIUS_API_KEY` | enable NVIDIA Nemotron deep review | offline linter only (fully functional) |
| `NEBIUS_BASE` | Nebius Token Factory base | `https://api.tokenfactory.nebius.com/v1/` |
| `NEBIUS_MODEL` | NVIDIA model id | `nvidia/nemotron-3-super-120b-a12b` |
| `TAVILY_API_KEY` | enable best-practice search enrichment | skipped |
| `PORT` | web server port | `8000` |

---

## Project layout

```
patchpilot/
├── patchpilot/
│   ├── lint.py       # deterministic offline linter (12 rules) + mechanical patches
│   ├── llm.py        # Nebius Token Factory + NVIDIA Nemotron reviewer + Tavily search
│   ├── agent.py      # PatchPilot.review() agentic loop
│   ├── receipts.py   # text + HTML report
│   ├── web.py        # stdlib web console (reads PORT)
│   └── cli.py        # command-line entry
├── eval.py           # 37-assertion offline self-test
├── server.py         # web entry point
├── examples/         # bad_code.py (planted issues)
├── render.yaml       # one-click cloud deploy
└── DESIGN.md
```

## License

MIT © Zhiyilang — see [`LICENSE`](LICENSE).
