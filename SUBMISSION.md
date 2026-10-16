# PatchPilot — Devpost submission copy (Nebius × NVIDIA Global AI Hackathon)

Deadline **Oct 30, 2026 6:00pm GMT+1** (= **Oct 31, 01:00 Beijing**).
Repo: `https://github.com/Zhiyilang/patchpilot` · Track: **Coding and Agentic Engineering**.
Also opt in to **Best Use of Tavily ($3,000)** and **Most Valuable Feedback ($100 × 10)**.

---

## 1. Project name

`PatchPilot 🩹 — an agentic code reviewer on Nebius + NVIDIA Nemotron`

## 2. Tagline (≤ 100 chars)

`Paste code, get a review with citations that had to pass a gate before they were believed.`

## 3. Track

**Coding and Agentic Engineering Track** — coding agents and developer tools.

## 4. Description (paste as-is)

### What it does

PatchPilot is an agentic code reviewer. You paste a Python file; it runs a real multi-step
agent loop — `PERCEIVE → LINT → REASON → RETRIEVE → PLAN → EXPLAIN → RECEIPT` — and returns
findings with line numbers and evidence lines, before/after patch diffs, and citations.

Two design rules drive everything:

1. **The model is never the only brain.** A deterministic 12-rule linter runs first and always.
   NVIDIA Nemotron (via Nebius Token Factory) adds semantic depth on top. If the model is slow,
   unconfigured, or unaffordable, the review still completes — and the receipt states which
   brain produced it. Nothing is silently downgraded.
2. **Tavily proposes. The gate decides what counts as evidence.** A retrieved page is a
   *candidate*, not a citation.

### How it uses Nebius Token Factory + NVIDIA Nemotron

`POST https://api.tokenfactory.nebius.com/v1/chat/completions` with
`model=nvidia/nemotron-3-super-120b-a12b`, `temperature=0` and
`response_format={"type":"json_object"}`. One completion returns **both** findings and patches
(`{"findings": [...], "patches": [...]}`), so a review costs one call instead of two. The
OpenAI-compatible surface meant the whole integration was two strings: base URL and model id —
I built and tested the offline brain first and swapped Nemotron in without touching the agent
loop.

### How it uses Tavily — the evidence layer

Five endpoints wrapped in pure `urllib` (no SDK): `/search`, `/extract`, `/map`, `/crawl`,
`/research`, plus `GET /usage` for credit accounting.

Retrieval intent is derived **deterministically** from the finding, not hallucinated by a
model: `EVAL_EXEC` and `HARDCODED_SECRET` become a CVE hunt
(`topic=news`, `search_depth=advanced`, `include_domains=[cwe.mitre.org, nvd.nist.gov,
owasp.org, github.com]`, `include_domains_mode=filter`); `BARE_EXCEPT`, `MUTABLE_DEFAULT` and
friends become an official-docs lookup (`topic=general`, `docs.python.org`). `TODO_FIXME`
gets no search at all — it does not deserve budget.

Every candidate then faces a gate, and **every rejection is recorded with its reason and shown
in the receipt**:

1. domain blocklist (content farms),
2. authority tier — `cwe.mitre.org` / `nvd.nist.gov` / `owasp.org` / `docs.python.org` /
   `*.readthedocs.io` above community sources above everything else,
3. URL de-duplication after normalisation (tracking params stripped),
4. keyword must-match — a page that never says `cve` / `vulnerab` / `injection` is not evidence
   for that finding,
5. **quote verification** — `extract` pulls the body and the snippet's longest keywords are
   checked against it. Only then is a citation marked `quote_verified: true`. Unverified stays
   visibly unverified.

Budgets are explicit (`max_search`, `max_extract`), high-severity findings are researched
first, and real `usage.credits` are printed on the receipt.

### Built with

Python 3 standard library only — **zero dependencies**, no `pip install`. `urllib` for HTTP,
`http.server` for the web console, `re` for the linter.

### What I'm proud of

`python eval.py` runs **91 assertions** offline, most of them written against the evidence
layer with a fake Tavily client: the gate rejecting content farms, low-tier domains, duplicates
and keyword misses; budgets capping calls and credits; quote verification passing and failing;
HTTP errors degrading instead of crashing; and the whole review completing with zero keys. The
suite is the reason I trust the "never blocks the review" claim.

### Try it

```bash
git clone https://github.com/Zhiyilang/patchpilot && cd patchpilot
python eval.py                                   # 91/91, no keys needed
python -m patchpilot.cli examples/bad_code.py --offline-evidence
export NEBIUS_API_KEY=...                        # Nebius → Token Factory
export TAVILY_API_KEY=...                        # tavily.com free tier
python -m patchpilot.cli examples/bad_code.py --search --evidence-json ev.json
python server.py                                 # web console, reads PORT
```

## 5. Demo video

`<3 min YouTube link>` — script in `DEMO_SCRIPT.md`.

## 6. Public repository

`https://github.com/Zhiyilang/patchpilot` — MIT licence visible at the top of the page.

## 7. Feedback on Nebius Token Factory, AI Cloud and NVIDIA tools

See `NEBIUS_FEEDBACK.md` (also linked from the repo root). Summary of the asks, ranked:

1. A usage / remaining-balance endpoint or response header — budget visibility is the top
   blocker for agent loops.
2. A documented machine-readable error taxonomy (`auth_error` / `rate_limited` /
   `model_unavailable` / `context_too_long`) plus `Retry-After`, so clients can fall back
   intelligently instead of bluntly.
3. Published p50/p95 latency and cold-start numbers with a recommended client timeout.
4. Tavily: a per-result authority signal, so every agent builder stops maintaining a private
   domain blocklist.

## 8. Prize categories to tick

- [x] **Coding and Agentic Engineering Track**
- [x] **Best Use of Tavily** ($3,000) — the evidence layer is the core differentiator
- [x] **Most Valuable Feedback** ($100) — `NEBIUS_FEEDBACK.md`
- [ ] City Winner Award — only if you attended an in-person Builders & Brews; skip otherwise

## 9. Judging-criteria self-check

| Criterion | Where it's answered |
|---|---|
| Technological Implementation | Token Factory `/chat/completions` + Nemotron with strict JSON mode, one call for findings+patches; five Tavily endpoints; deterministic gate |
| Design | Complete product: CLI + web console + HTML receipt; degrades to offline without breaking |
| Potential Impact | Real reviewer workflow: line numbers, evidence lines, applyable diffs, citations that had to earn their place |
| Quality of Idea | "The model is never the only brain" + "Tavily proposes, the gate decides" — non-obvious use of retrieval as *gated* evidence rather than decoration |
