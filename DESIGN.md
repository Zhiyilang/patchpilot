# PatchPilot — Design Notes

## Why dual-brain

A code reviewer that only works with an API key is a demo that dies the moment the key
expires or the network blips during judging. PatchPilot separates two concerns:

- **Offline linter (`lint.py`)** — deterministic, zero-dependency, always available. 12 real
  rules with mechanical patches. This is the floor: a genuinely useful tool with no key.
- **Nemotron reviewer (`llm.py`)** — deep semantic review (bugs, security, correctness) via
  **Nebius Token Factory** (OpenAI-compatible) with **NVIDIA Nemotron**. This is the ceiling.

`PatchPilot.review()` runs the linter unconditionally, then the Nemotron reviewer if a key is
present. If the Nebius call fails (auth/network/rate), it is caught and the review continues
offline — the demo never 500s. Findings from both brains are merged and de-duplicated by
`(code, line)`.

## The agentic loop

`PERCEIVE → LINT → REASON → RETRIEVE → PLAN → EXPLAIN → RECEIPT`. RETRIEVE is optional
Tavily search that attaches current best-practice references to high-severity findings
(a separate hackathon track prize). Every step is inspectable in the returned dict.

## Nebius / NVIDIA wiring

Nebius Token Factory is OpenAI-compatible, so the reviewer is a plain
`POST {base}/chat/completions` with `Authorization: Bearer $NEBIUS_API_KEY`,
`response_format: json_object`, and `model: nvidia/nemotron-3-super-120b-a12b`. The system
prompt forces strict JSON (`findings` + `patches`); parsing is defensive and per-finding, so
one malformed entry never drops the whole review.

## Deterministic linter pitfalls handled

- Comment lines are only scanned for TODO markers (not treated as code).
- `SWALLOWED_EXCEPT` is a two-line rule (`except …` followed by `pass …`), tolerant of
  trailing comments.
- Every finding carries `evidence` (the matched line) and a `line` number for traceability.

## Testing

`eval.py` is offline and deterministic: it asserts all 12 rules fire on the planted-bug
sample, that mechanical patches are produced, that the agent loop works in offline mode,
that **clean code yields zero findings** (negative test), that de-duplication merges both
brains correctly, and that the HTML receipt renders. A Nebius live test runs only when
`NEBIUS_API_KEY` is set (skipped otherwise, still passing).

## From demo to production

Add a persistent cache for Nemotron results, stream large files in chunks, and expand the
linter to more languages (the rule table is data-driven, so adding languages is additive).
