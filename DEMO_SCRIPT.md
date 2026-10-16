# PatchPilot demo script — 2:50

Target: **under 3 minutes** (Nebius cap). One take, no cuts needed if you follow the beats.
Record 1080p, terminal font ≥ 16px, browser at 125% zoom.

**Before you press record**

```bash
cd patchpilot
export NEBIUS_API_KEY=...      # Nebius → Token Factory
export TAVILY_API_KEY=...      # tavily.com → free tier (skip if not yet approved)
python eval.py                 # expect: 91 passed / 0 failed
```

If either key is missing, use the fallback line marked **[NO-KEY]** in each beat. The demo still
works; say the bracketed sentence out loud — it is a feature, not an apology.

---

## 0:00–0:14 — Hook

**Screen:** terminal, empty.
**Say:** "This file has four bugs that cost real money. I'm going to let an agent find them,
prove why they matter, and hand me the fix — in one command."
**Do:** `cat examples/bad_code.py` — let the planted `eval(`, hardcoded `AWS_KEY`, bare
`except:`, `== None` scroll past.

## 0:14–0:38 — The offline brain (works with zero keys)

**Do:** `python -m patchpilot.cli examples/bad_code.py --no-llm`
**Say:** "A deterministic linter runs first: twelve real Python rules — line numbers, evidence
lines, and mechanical before/after patches. No API key, no network. This is the floor: it never
gets worse than this."
**Point at:** the risk score, the three HIGH findings, the diff lines.

## 0:38–1:10 — Nemotron on Nebius Token Factory

**Do:** `python -m patchpilot.cli examples/bad_code.py --html report.html`
**Say:** "Now the same loop with **NVIDIA Nemotron** through **Nebius Token Factory**. One
completion returns both findings and patches — I pay once, not twice. `temperature=0` and
strict JSON mode are what make that safe."
**Point at:** `大脑：offline+nemotron`, `🧠 本轮启用了 NVIDIA Nemotron`.
**[NO-KEY]** "No key configured, so the offline brain produced this one instead — and the
receipt says exactly which brain did the work. Nothing is silently downgraded."

## 1:10–2:00 — The evidence layer (the differentiator)

**Do:**
```bash
python -m patchpilot.cli examples/bad_code.py --search --evidence-json ev.json
python -m patchpilot.cli --usage            # live credit accounting
```
**Say:** "Here's the part I care about. Most tools paste whatever search returns straight into
the report. PatchPilot treats every retrieved page as a **candidate**. Look at the gate line:
candidates in, admitted out. Content farms rejected. Low-authority domains rejected. Duplicate
URLs rejected. Pages that never mention the keyword rejected — and every rejection is listed
with its reason."
**Point at:** `🧭 证据闸门：候选 N → 采纳 M`, `端点 {...}`, `credits`.
**Say:** "Then the top results get `extract`ed and the snippet's keywords are checked against
the real page body. Only then is it marked verified. Unverified stays visibly unverified."
**Point at:** `✅ 已回正文核对`.
**[NO-KEY]** run `--offline-evidence` instead, and say: "No key yet, so this is running on
built-in fixtures — note they're labelled `fixture` and none are marked verified. I'd rather
show you an honest blank than a fake citation."

## 2:00–2:25 — Web console

**Do:** `python server.py`, open `http://localhost:8000/app`, paste the sample, tick
**Tavily 证据检索**, submit.
**Say:** "Same engine, hosted console — reads `PORT`, ships on Render with one click."
**Point at:** the receipt's evidence block with domain + authority tier per citation.

## 2:25–2:50 — Close

**Do:** `python eval.py` one more time (or keep the 91/91 from the top).
**Say:** "Two rules everything here follows. **The model is never the only brain** — a
deterministic checker runs first, always. And **Tavily proposes, the gate decides** — a
retrieved page isn't evidence until a rule admits it and the quote is checked at the source.
Eighty-three assertions, zero dependencies, MIT. That's PatchPilot."

---

## YouTube metadata

**Title:** PatchPilot — an agentic code reviewer on Nebius Token Factory + NVIDIA Nemotron
where search results have to pass a gate

**Description:**
> PatchPilot is an agentic code-review agent built for the Nebius × NVIDIA Global AI Hackathon.
> It runs on Nebius Token Factory with NVIDIA Nemotron (nvidia/nemotron-3-super-120b-a12b) and
> falls back to a deterministic 12-rule offline linter when no key is present, so it demos with
> zero setup.
>
> The evidence layer is the interesting part: retrieved pages are only *candidates*. A
> deterministic gate applies a domain blocklist, authority tiers, URL de-duplication and
> keyword must-match, then Tavily's /extract pulls the page body so quoted keywords can be
> verified against their source. Rejections are shown with reasons; unverified citations are
> never labelled verified.
>
> Pure Python standard library. 91 offline assertions. MIT.
>
> Repo: https://github.com/Zhiyilang/patchpilot
> Feedback on Nebius + Tavily: NEBIUS_FEEDBACK.md

**Tags:** `nebius`, `nvidia nemotron`, `token factory`, `ai agent`, `code review`, `tavily`,
`hackathon`, `devpost`, `python`, `llm agent`, `static analysis`
