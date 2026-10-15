# Feedback on Nebius Token Factory, NVIDIA Nemotron & Tavily

*Submitted for the **Most Valuable Feedback** category of the Nebius × NVIDIA Global AI
Hackathon. Written by the author of PatchPilot (github.com/Zhiyilang/patchpilot).*

**Honesty note first:** the integration work and the 83-assertion offline suite are done and
shipped, but at the time of writing the live `NEBIUS_API_KEY` had not yet been provisioned on
my account. Everything marked **[measured]** below comes from code paths that run locally;
everything marked **[integration-time]** is an observation made while writing against the API
surface, not a benchmark. I would rather say so than invent latency numbers. If the key lands
before judging, I will re-run and replace the **[integration-time]** markers with real figures.

---

## 1. What I built against your stack

PatchPilot is an agentic code reviewer. The loop is
`PERCEIVE → LINT → REASON → RETRIEVE → PLAN → EXPLAIN → RECEIPT`.

- **REASON** = `POST {NEBIUS_BASE}/chat/completions` with
  `model=nvidia/nemotron-3-super-120b-a12b`, `temperature=0`,
  `response_format={"type":"json_object"}`, one call returning both findings and patches so I
  pay for one completion instead of two.
- **LINT** = a deterministic 12-rule Python linter that runs *before* and *independently of*
  the model, and is the fallback brain.
- **RETRIEVE** = Tavily evidence layer (section 4).

Everything is pure Python standard library — no SDK, no `pip install`. `python eval.py` runs
83 assertions offline.

---

## 2. Nebius Token Factory — what worked

**[measured]** The OpenAI-compatible surface is genuinely drop-in. I wrote the reviewer
against `/chat/completions` with a `Bearer` header and never needed Nebius-specific code. The
single change from any other OpenAI-compatible provider was two strings: the base URL and the
model id. That is the whole migration cost, and it is the reason the offline fallback could be
developed first and swapped in later without touching the agent loop.

**[measured]** `response_format: json_object` returning strict JSON is what made the "one call,
two outputs" design viable. I ask for `{"findings": [...], "patches": [...]}` in one shot and
parse it once. Without guaranteed JSON object output I would have needed two calls or a
fragile regex scrape.

**[integration-time]** `temperature=0` plus a JSON schema in the system prompt is the right
combination for a deterministic-feeling reviewer. My system prompt is short and structural
("output JSON only, do not explain"), and I keep the user turn to the first 12,000 characters
of the file — enough for real files, bounded enough to be predictable.

---

## 3. Friction, and what I had to build around it

These are the things that cost me engineering time. Ordering is by how much time they cost,
not by severity.

### 3.1 A long model id is a footgun for newcomers **[integration-time]**

`nvidia/nemotron-3-super-120b-a12b` is precise and I understand why it is precise — but it is
also 33 characters of vendor/model/variant/quantisation that a first-time user has to
transcribe correctly from a docs page. A typo here fails at request time, not at config time.

**What I did:** isolated it behind `NEBIUS_MODEL` with the full id as the default, so a user
never types it and my code never hardcodes a guess.

**Suggestion:** ship a `GET /v1/models` filter (or a copyable "model id" chip next to each
card in the Token Factory playground) and, on a 404 for an unknown model, return the three
closest available ids in the error body. That single error-message improvement would remove
most first-hour attrition.

### 3.2 Failure semantics are not observable enough to build a good fallback **[integration-time]**

When a provider call fails, the client has to decide instantly: retry, fall back, or abort.
That decision needs to distinguish *auth failure* from *rate limit* from *model overloaded*
from *malformed output*. Today I collapse everything into one `except Exception` and fall back
to the offline linter, which is safe but blunt — a 401 and a 429 get the same treatment.

**What I did:** wrapped the call so any failure flips `nemotron_used=False` and the review
still completes with the offline brain. The receipt always states which brain produced it, so
the user is never shown a silent downgrade.

**Suggestion:** document a stable machine-readable error taxonomy (`error.type` values such as
`auth_error`, `rate_limited`, `model_unavailable`, `context_too_long`) and put
`Retry-After` on 429s. Client authors can then do the right thing without string-matching
messages.

### 3.3 No visible budget before the bill **[integration-time]**

I am capping my own calls (`max_search`, `max_extract`, one completion per review) because I
cannot see remaining credits from inside my program. Every hackathon participant who builds an
agent loop will hit this: an agent that retries or fans out can burn a student-sized credit
balance in one afternoon with no warning.

**Suggestion:** a `GET /v1/usage`-style endpoint (or an `x-remaining-credits` response header)
returning remaining balance and burn rate. Tavily already returns `usage.credits` per call and
I surface it directly in my receipt — I would do the same for Nebius in a heartbeat. This is
the single highest-leverage developer-experience addition I can think of.

### 3.4 Cold-start and timeout guidance is missing **[integration-time]**

I set `timeout=60` for the review call. That number is a guess. For a long file it may be too
short; for an interactive review loop it may be too long to sit on. Without published
first-token or cold-start characteristics, every client author guesses and then discovers the
answer in production.

**Suggestion:** publish p50/p95 time-to-first-token per model and an explicit recommended
client timeout, plus whether the endpoint keeps a warm pool. Even a rough table turns a guess
into a decision.

### 3.5 JSON object mode plus "do not explain" deserves a documented note **[integration-time]**

Strict JSON output is the feature that made my design work, and I nearly didn't use it because
it is easy to assume it means "the model will return valid JSON for anything". It doesn't — the
prompt still has to be structural. A short doc note ("json_object constrains the shape, not the
content; keep the schema in the system prompt and keep it small") would save people a debugging
cycle. I additionally parse defensively with
`content[content.find("{"):content.rfind("}")+1]` because one stray sentence breaks
`json.loads`.

---

## 4. Tavily feedback (used for the evidence layer)

PatchPilot uses Tavily as an **evidence** layer, not a search box. Retrieved pages are
candidates; a deterministic gate decides what becomes a citation.

**What worked well:**

- **[measured]** `include_domains` + `include_domains_mode: "filter"` is the single most useful
  parameter in the API. It lets me express intent — "for a CVE hunt only look at
  `cwe.mitre.org`, `nvd.nist.gov`, `owasp.org`, `github.com`" — and moves a chunk of my
  relevance problem onto an API that is better at it than my regexes.
- **[measured]** `topic=news` for advisories vs `topic=general` for documentation is a real
  distinction, not a decorative one: the same query returns materially different result sets,
  and news mode is what makes the CVE intent worth running.
- **[measured]** `extract` returning clean markdown is what makes quote verification possible
  at all. I pull the body and check that the snippet's longest keywords actually appear in it
  before labelling a citation `quote_verified`. Without `extract` this feature would be
  theatre.
- **[measured]** `usage.credits` per response is excellent. I surface it in the receipt, so the
  cost of a review is visible to the person who ran it.

**Friction:**

- **[integration-time]** Credit cost is depth-dependent (`advanced` costs more) and
  `auto_parameters` can silently upgrade a request. For anyone on a metered key, "I asked for
  basic and got charged for advanced" is a bad surprise. The `usage.credits` field saves this
  from being invisible, but a `requested_depth` / `effective_depth` pair in the response would
  make it explicit.
- **[integration-time]** `extract` currently returns one body per URL with no per-URL success
  flag beyond `failed_results`. A per-result `status` alongside `raw_content` would let clients
  distinguish "page empty" from "fetch failed" without cross-referencing two arrays.
- **[integration-time]** `/research` is asynchronous with a polling flow, which is the right
  design, but there is no documented recommended poll interval or terminal-state list. A
  one-line note would stop every implementer from inventing their own.

**Suggestion, highest value first:** a first-class *authority* signal. I maintain a
hand-written domain tier list (authoritative / community / other / blocked). It works, and it
is also exactly the kind of thing that rots silently and that every agent builder is
reimplementing in private. A per-result `source_authority` score — even a coarse one — would let
clients drop their blocklists and would make "don't cite content farms" a platform guarantee
instead of a per-project chore.

---

## 5. What I'd ask for, ranked

1. **Nebius:** a usage/balance endpoint or header. Budget visibility is the top blocker for
   agent loops.
2. **Nebius:** a documented, machine-readable error taxonomy + `Retry-After`. Clients can then
   fall back intelligently instead of bluntly.
3. **Nebius:** published latency/cold-start numbers with a recommended client timeout.
4. **Tavily:** a per-result authority signal, so every agent builder stops maintaining a private
   domain blocklist.
5. **Both:** make credit cost explicit *before* the call, not just after it.

---

## 6. The pattern I'd recommend to other builders

The most useful thing I learned building this is architectural, and it only exists because
both providers can be unavailable:

> **The model is never the only brain.** Run a deterministic checker first, always. Let the
> model add depth on top. If the model is slow, absent, or unaffordable, the product still
> ships a real answer — and the receipt says which brain produced it.

Same rule for retrieval: **Tavily proposes, the gate decides.** A retrieved page is not
evidence until a deterministic rule admits it and the quote is checked against the source.
That is why PatchPilot can be demoed with no keys at all, and why the demo is honest about
what it did not verify.
