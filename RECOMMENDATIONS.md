# Pipeline Optimization Recommendations for Claude Fable 5

**Date:** 2026-06-10
**Scope:** Evaluation of the six-agent adversarial build pipeline (Clarifier → Planner →
Generator → Architect → Design Critic → Evaluator) against **Claude Fable 5**
(`claude-fable-5`, GA 2026-06-09), to which this project's sessions have been switched.
**Status:** Recommendations only — no pipeline files have been modified.

All Fable 5 facts below are sourced from Anthropic's published docs (models overview,
"Introducing Claude Fable 5 and Claude Mythos 5," the Opus 4.8 → Fable 5 migration guide,
and "Prompting Claude Fable 5"), fetched 2026-06-10.

---

## 1. What changed with Fable 5 (relevant facts)

| Dimension | Opus 4.8 (current pipeline target) | Claude Fable 5 |
|---|---|---|
| Model ID | `claude-opus-4-8` | `claude-fable-5` |
| Pricing | $5 / $25 per MTok | **$10 / $50 per MTok (2×)** |
| Context / max output | 1M / 128K | 1M / 128K (same tokenizer — token counts roughly unchanged) |
| Thinking | Adaptive, off unless set | **Adaptive, always on**; `thinking: {type: "disabled"}` returns 400 |
| Thinking output | `display: "omitted"` default | Raw CoT **never** returned; `summarized` or `omitted` only |
| Effort guidance | `xhigh` for coding/agentic | **`high` is the recommended default**; reserve `xhigh` for the most capability-sensitive work; lower levels often beat prior-model `xhigh` |
| Safety classifiers | None | **Yes** — can return `stop_reason: "refusal"` (HTTP 200) with `stop_details.category` ∈ `cyber`, `bio`, `reasoning_extraction`, … Benign security work can trigger them |
| Fallback | n/a | `fallbacks` param (beta), SDK middleware, or manual retry; fallback credit refunds prompt-cache cost |
| Prompt-cache minimum | 1,024 tokens | **512 tokens** |
| Data retention | ZDR available | **30-day retention required; not available under ZDR** (400 otherwise) |
| Turn length | Minutes | **Much longer turns by default**; autonomous runs can extend for hours |
| Subagents | Conservative; needs prompting | **Significantly more dependable at parallel subagent dispatch and sustained communication** |
| Prescriptive prompts | Tolerated | **Over-prescriptive skills/prompts can degrade output quality** — brief instructions steer as well as enumerations |

---

## 2. High-priority recommendations

### 2.1 Add refusal/fallback handling as an orchestrator responsibility ⚠️ (most important)

This pipeline is unusually exposed to Fable 5's safety classifiers:

- The **Evaluator's security probes** (Directive 5) instruct entering injection payloads
  (`'; DROP TABLE users; --`), issuing unauthenticated requests against protected
  endpoints, and IDOR identifier-swapping.
- The **attack-library Security shard** is, by design, a growing library of
  exploit-shaped probes.
- Anthropic explicitly warns: *"Benign cybersecurity work … may also trigger these
  safeguards."*

A mid-build refusal (`stop_details.category: "cyber"`) during an Evaluator security pass
would currently look like a silent agent failure with no defined recovery path.

**Recommend:**

1. Add **Orchestrator Responsibility #15 — Refusal handling**: if any sub-agent
   invocation ends with `stop_reason: "refusal"`, log the `stop_details.category` to
   `pipeline-state/progress.md` and retry that invocation on `claude-opus-4-8`
   (per Anthropic's own guidance: *"configure server-side or client-side fallback to
   Claude Opus 4.8"*). Do not consume a round. Where the harness supports it, use the
   beta `fallbacks` parameter or the SDK refusal-fallback middleware instead of a manual
   retry.
2. Consider **pinning the Evaluator's security-probe portion to Opus 4.8** outright
   (e.g., run security probes in a dedicated Opus 4.8 subagent) so the most
   refusal-prone work never hits the classifier. Functional/spec testing stays on
   Fable 5, where its improved bug-finding recall pays off.
3. In the attack-library schema, add an optional `Refusal-risk:` field on Security-shard
   probes so the orchestrator knows which probes to route to the fallback model.

### 2.2 Audit prompts for `reasoning_extraction` triggers

Fable 5 refuses requests that ask it to *echo, transcribe, or explain its internal
reasoning as response text* (`reasoning_extraction` category). The pipeline's
"reason-before-verdict" cues are mostly safe (they ask the model to think, not to
transcribe thinking), but three files contain stale or risky phrasing:

- `evaluator.md` (Grading Criteria): *"This reasoning benefits from extended thinking;
  the harness should grant the Evaluator a thinking budget."*
- `architect.md` / `design-critic.md` (Pass/Fail Decision): *"(This benefits from
  extended thinking where the harness grants the … a budget.)"*
- `README.md` § Optimized for Opus 4.8: the "thinking budget" note.

**Recommend:** Replace all "extended thinking / thinking budget" references with
"adaptive thinking (always on for Fable 5); thinking depth is controlled by `effort`."
`budget_tokens` has been removed since Opus 4.7 and `thinking: disabled` now errors —
this phrasing is doubly obsolete. While auditing, confirm no agent instruction asks the
model to *reproduce* its reasoning in a report body (the structured "Verdict Summary /
Evidence" format is fine; "show your full reasoning" would not be).

### 2.3 Parallelize the Architect and Design Critic

The two mid-pipeline discriminators are nearly independent — the Architect reads code
and never starts the app; the Design Critic uses the live app and never reads code. The
only coupling is that the Design Critic reads `architecture_review_round_N.md` "for
context" (explicitly *not* to duplicate it), and the serial gate that an Architect FAIL
triggers a Generator revision before the Design Critic runs.

Fable 5 is *"significantly more dependable at dispatching and sustaining parallel
subagents"*, and Anthropic recommends preferring *"asynchronous communication … over
blocking until each subagent returns."*

**Recommend:**

1. Run Architect and Design Critic **concurrently** after each Generator build/revision.
2. On any FAIL, hand the Generator **one combined revision pass** with both reports,
   instead of two sequential single-dimension passes.
3. Drop the Design Critic's read of the current round's architecture review (move the
   "what was structurally revised" context to `pipeline-state/progress.md`, which it
   already reads).

Payoff: roughly halves reviewer wall-clock per round, and removes most of the
"Coordinated Revision Passes" machinery (Generator Directive 10) — the
second-pass-undoes-first-pass hazard and much of the `CONFLICT.md` surface exist only
because the two revisions are sequential today. One combined pass eliminates the
ordering problem at the source.

### 2.4 Re-tier effort and model per agent (cost control at 2× pricing)

Fable 5 costs 2× Opus 4.8. The pipeline runs up to 7 rounds with three reviewers per
round — left untiered, build cost roughly doubles. Anthropic's guidance: default
`high` (not `xhigh`), since *"lower effort settings on Claude Fable 5 still perform well
and often exceed `xhigh` performance on prior models."*

**Recommend** the following assignment (agent `model:` frontmatter + harness effort):

| Agent | Model | Effort | Rationale |
|---|---|---|---|
| Clarifier | `claude-sonnet-4-6` or Opus 4.8 | medium | No tools, single structured output; capability-insensitive |
| Planner | `claude-fable-5` | high | Spec quality cascades through everything downstream |
| Generator | `claude-fable-5` | high (try `xhigh` only on builds that stall) | The capability-sensitive core; Fable's first-shot correctness is the main win |
| Architect | `claude-fable-5` | high | Benefits from improved codebase-search/bug-finding recall |
| Design Critic | `claude-fable-5` | high | Improved vision: *"interprets dense technical images, web applications, and detailed screenshots with substantially higher accuracy"* — directly relevant to 3-viewport screenshot review |
| Evaluator | `claude-fable-5`, **security probes on Opus 4.8** | high | See §2.1 |

Also: make **Orchestrator Responsibility #8 (cost tracking)** non-optional — set a
default per-build cost threshold (currently "default: none") now that per-token price
doubled, and record `stop_details`/fallback events in `cost.md` since refused-then-
retried calls have their own billing rules (refused-before-output requests are free;
fallback credit refunds the prompt-cache cost of switching).

### 2.5 Recalibrate the adversarial game for higher first-shot correctness

Fable 5 shows *"first-shot correctness on complex, well-specified problems — single-pass
implementations of systems that previously took days of iteration."* The pipeline's spec
is exactly the "well-specified problem" shape. Expect Generator WINs in rounds 1–2 to
become common, which has two effects on the game:

1. **The threshold ratchet (5.5 → 6.5 → 7.5) rarely engages.** If builds routinely pass
   round 1 at ≥5.5, the ratchet no longer pressures quality. Recommend raising the
   round-1 threshold (e.g., 6.5 / 7.0 / 7.5) **after re-baselining on 2–3 real builds**
   — change `THRESHOLDS` in `.claude/scripts/score.py` and the mirror table in
   `value-function.md` in lockstep, as documented.
2. **The 7-round cap is likely oversized.** Consider 5 rounds; a Fable 5 build that
   fails 5 consecutive rounds almost certainly has a spec problem
   (`ESCALATION_REQUESTED.md` territory), not a generation problem.
3. **The attack library matters more, not less.** With the Generator stronger, the
   discriminators' edge comes from the growing probe library. Keep the discovery-gated
   novelty rule, and lean on Fable's memory strength (§2.7) to make harvesting richer.

---

## 3. Prompt-level recommendations (per agent)

### 3.1 De-prescribe the agent prompts (all six)

Anthropic, on Fable 5: *"Skills developed for prior models are often too prescriptive
for Claude Fable 5 and can degrade output quality. Review and consider removing older
instructions if default performance is better."* And: *"you can steer most behaviors
with a brief instruction rather than enumerating each behavior by name."*

The agent files are heavily enumeration-styled (generator.md is ~600 lines; the stub
examples, revision-category catalogs, and repeated "This is not optional" emphasis were
written to overcome weaker models' drift). Recommend a slimming pass per agent:

- Keep: concrete contracts (file formats, format-version headers, SCORE-BLOCK schemas,
  severity rubrics, the Design Critic's banned-widget-words list — these are
  *specifications*, not behavioral nagging).
- Trim: repeated imperative emphasis ("Do not… This is not optional… No exceptions"),
  long example catalogs that illustrate a one-line principle, and "you are prone to X"
  framing. One brief statement of each principle suffices on Fable 5.
- A/B this on one build before committing — the doc's advice is "review and consider,"
  not "delete."

### 3.2 Generator

- **Add the grounded-progress-claims instruction** to Directive 15 (`VERIFY_NOTES.md`).
  Anthropic's snippet (*"Before reporting progress, audit each claim against a tool
  result from this session… Report outcomes faithfully: if tests fail, say so with the
  output"*) *"nearly eliminated fabricated status reports"* in their testing. This
  directly hardens the Generator-self-report vs. Evaluator-live-test divergence check.
- **Add the anti-overengineering snippet** to the two revision modes (Directives 7–8).
  Fable 5 at high effort tends toward unrequested tidying/refactoring; the revision
  modes already say "scope your changes to the findings," and Anthropic's snippet
  (*"Don't add features, refactor, or introduce abstractions beyond what the task
  requires…"*) is the tested phrasing.
- **Add the autonomous-operation reminder** (no mid-task permission-asking; before
  ending a turn, check the last paragraph isn't an unexecuted promise). Fable 5 can
  occasionally end a turn with "I'll now run X" without the tool call — in an
  unattended multi-hour pipeline that's a stall. `ESCALATION_REQUESTED.md` remains the
  sanctioned channel for genuine product questions.
- **Update Directive 5's model-ID guidance** for generated apps: add `claude-fable-5`
  to the lineup ("Fable for the hardest reasoning at 2× Opus pricing — and only with
  refusal/fallback handling wired in; Opus 4.8 for hard reasoning; Sonnet for the
  common case; Haiku for cheap/fast tool loops"). Generated products that pick Fable 5
  must handle `stop_reason: "refusal"` — that's a spec-level consideration the
  Architect's AI-integration sub-dimension should also check.
- **Avoid surfacing token countdowns.** Fable 5 can prematurely wrap up when shown
  remaining-context counts. `cost.md` is orchestrator-side (fine); just don't inject
  budget numbers into Generator prompts. If the harness must, include Anthropic's
  "You have ample context remaining" reassurance.

### 3.3 Design Critic & Evaluator — remove the blocking "ask the user" step

Both agents' Step 3 halts the pipeline to ask the user to confirm browser tooling
("Do not proceed until the user has responded"). Two problems on Fable 5: (a) the
model is steered to avoid mid-task permission questions, and the instruction fights
that; (b) it blocks an otherwise-autonomous multi-hour run on a human keystroke.

**Recommend:** replace with capability *detection* — attempt the configured browser
tool (e.g., Playwright MCP); only if unavailable, write `ESCALATION_REQUESTED.md`
(the existing no-round-consumed pause mechanism) instead of an inline question.

### 3.4 Reviewers (Architect, Design Critic, Evaluator)

- Keep the reason-before-verdict steps — they align with always-on adaptive thinking —
  but reword per §2.2.
- **Lead-with-the-outcome reporting:** the report templates already put Verdict and
  Verdict Summary first; add Anthropic's brevity guidance ("be selective about what you
  include; don't compress into fragments/arrow chains") to the report-voice
  instructions so long Fable-5 reports stay readable for the Generator.
- **Fresh-context verification:** Anthropic notes *"separate, fresh-context verifier
  subagents tend to outperform self-critique."* The pipeline's discriminator design is
  already exactly this — worth stating in the README as a Fable-5-aligned property, and
  worth extending: the Generator's Phase 7 (Verify) could spawn a fresh-context
  verification subagent rather than self-checking, catching defects one round earlier
  at Generator (not Evaluator) cost.

---

## 4. Harness / infrastructure recommendations

1. **Raise timeouts and check asynchronously.** *"Individual requests on hard tasks can
   run for many minutes at higher effort settings… autonomous runs can extend for
   hours. Adjust client timeouts, streaming, and user-facing progress indicators before
   migrating."* The per-feature `session.md` checkpoint + Resume Protocol already make
   interruption cheap — keep them; they're the right design for Fable-5-length runs.
2. **Prompt caching:** minimum cacheable prefix drops to 512 tokens on Fable 5. The
   attack-library's stable-first shard ordering and byte-stable agent prompts are
   already cache-correct; after any prompt-slimming pass (§3.1), re-freeze the prefixes.
3. **Data retention gate:** Fable 5 requires 30-day retention and is unavailable under
   ZDR (400 `invalid_request_error`). If this org ever moves to ZDR, the pipeline needs
   the Opus 4.8 fallback anyway (§2.1) — one more reason to wire it now.
4. **Thinking config hygiene:** remove any `thinking: {type: "disabled"}` or
   `budget_tokens` from harness configuration — both error on Fable 5. No `thinking`
   field needed at all; control depth with `effort` only.
5. **README § "Optimized for Opus 4.8"** should become "Optimized for Claude Fable 5,"
   re-deriving each row: arithmetic still goes through `score.py` (unchanged —
   determinism, not capability, is the reason); literal instruction-following is
   stronger, so the prompt-slimming in §3.1 replaces the "aggressive emphasis" coping
   strategy; the model-lineup row adds `claude-fable-5` with the refusal caveat.

---

## 5. New capability to exploit: a Generator memory system

Anthropic: *"Claude Fable 5 performs particularly well when it can record lessons from
previous runs and reference them. Provide a place to write notes, as simple as a
Markdown file."*

The pipeline already gives the **discriminators** cross-build memory
(`attack-library.md`) but gives the Generator none — deliberately asymmetric. With
Fable 5, a bounded Generator memory improves build quality without unbalancing the
game, because it stores *defensive* lessons (what passed review), not reviewer secrets:

- Add `pipeline-state/playbook.md` — one lesson per entry, one-line summary on top,
  written by the Generator at the end of each build (seeded from `RETROSPECTIVE.md`'s
  "Persistent Failure Patterns"). Same append/dedup/retire discipline as the attack
  library. The Generator reads it at Session Startup step 4a.
- Keep it out of the reviewers' working sets so the discriminators' probe surface stays
  independent.
- Bootstrap per Anthropic's recipe: have Fable 5 review past builds' retrospectives
  with subagents and distill the core lessons.

---

## 6. Summary — ranked by impact

| # | Recommendation | Impact | Effort |
|---|---|---|---|
| 1 | Refusal/fallback handling (orchestrator resp. #15; security probes on Opus 4.8) | Prevents silent mid-build failures | Low |
| 2 | Parallelize Architect + Design Critic; one combined revision pass | ~½ reviewer wall-clock; removes CONFLICT-prone sequential revisions | Medium |
| 3 | Effort/model tiering per agent + default cost threshold | Contains the 2× price increase | Low |
| 4 | Remove obsolete thinking-budget wording; audit for reasoning-extraction triggers | Avoids 400s and refusals | Low |
| 5 | Grounded-progress + anti-overengineering + autonomy snippets in Generator | Better VERIFY_NOTES fidelity; cleaner revisions; no stalls | Low |
| 6 | Replace blocking browser-tool questions with detect-or-escalate | True end-to-end autonomy | Low |
| 7 | Prompt-slimming pass (de-prescribe), A/B'd on one build | Output quality per Anthropic guidance | Medium |
| 8 | Recalibrate ratchet/round-cap after 2–3 Fable 5 builds | Keeps the minimax game meaningful | Low (deferred) |
| 9 | Generator playbook memory (`pipeline-state/playbook.md`) | Compounding build quality across builds | Medium |
| 10 | Raise harness timeouts; keep checkpoint/resume as-is | Survives hours-long Fable 5 turns | Low |
