# Autonomous Build Pipeline

## Pipeline Overview
Six sub-agents: Clarifier → Planner → Generator → (Architect ∥ Design Critic) → Evaluator.
After each Generator build (or revision), the Architect (structural quality) and the Design
Critic (usability) review **concurrently** — they are independent: the Architect reads only
the code, the Design Critic uses only the live app. If either lands findings, the Generator
makes a **single combined revision pass** addressing both reports, then the Evaluator runs
functional tests. The Evaluator can trigger Generator re-runs up to 5 rounds — a Fable 5
build that fails 5 consecutive rounds almost certainly has a spec problem (escalation
territory), not a generation problem.

The pipeline is structured as an **adversarial minimax game**: the Generator
maximizes a shared scalar (the Acceptance Score, defined in
`pipeline-state/value-function.md`); the Architect, Design Critic, and
Evaluator collectively minimize it by landing confirmed defects. Per-round
outcomes are recorded as Generator-vs-Discriminator results in
`pipeline-state/scoreboard.md`, and confirmed defects are harvested into
`pipeline-state/attack-library.md` so the discriminators' test surface
grows monotonically across rounds and across builds. See "Adversarial
Game Mechanics" below.

Builds typically run in a **fresh clone of this template repository** — one
clone per build. A clone's `pipeline-state/` starts at the template's seed
state, and the files designed to compound across builds (`attack-library.md`,
`playbook.md`, `build-ledger.md`) flow back to the template through the
Harvest-Back Protocol below. Without that step, a build's lessons are
stranded in its clone.

## Long Turns Are Normal

Fable 5 turns on hard tasks run for many minutes at `high` effort, and a
full build can extend for hours. Do not treat a long-running sub-agent turn
as hung — `.claude/settings.json` raises bash and MCP tool timeouts, and the
per-feature `session.md` checkpoint plus the Resume Protocol make
interruption cheap. Check on a running build asynchronously (status checks
between agent invocations) rather than blocking on it; never inject
remaining-token or budget countdowns into a sub-agent's prompt — Fable 5 may
wrap up prematurely when shown one (cost accounting stays orchestrator-side
in `cost.md`).

## Model and Effort Tiering

Each sub-agent is pinned to a model in its agent-file frontmatter (`model:`).
Effort is a harness-level setting, not a per-agent frontmatter key — the
values below are operating guidance per Anthropic's Fable 5 recommendation
(default `high`; lower levels often exceed prior-model `xhigh`, so do not
reach for `xhigh` reflexively).

| Agent | Model | Effort guidance |
|---|---|---|
| Clarifier | `claude-sonnet-4-6` | medium — no tools, single structured output |
| Planner | `claude-fable-5` | high — spec quality cascades downstream |
| Generator | `claude-fable-5` | high; try `xhigh` only on builds that stall |
| Architect | `claude-fable-5` | high |
| Design Critic | `claude-fable-5` | high |
| Evaluator | `claude-fable-5` (security probes fall back to `claude-opus-4-8` — see Responsibility #15) | high |

## How to Run the Pipeline
- **Start a new build:** "Build [product concept]"
- **Resume an interrupted build:** "Resume build" — reads `pipeline-state/`
  files to determine where the pipeline was interrupted, then re-invokes the
  appropriate sub-agent.
- **Pause and add mid-flight input:** "Pause build: [feedback / change /
  question]" — appends the user's message to
  `pipeline-state/user-intervention.md`. The next Generator pass reads it and
  treats it as a late spec amendment. Use sparingly; mid-flight changes
  invalidate work already done.

## Orchestrator Responsibilities

The orchestrator (this top-level Claude Code session) owns these jobs that no
single sub-agent can:

1. **Round state.** Maintain `pipeline-state/round.md` as the single source of
   truth for the current round number; sub-agents read it instead of counting
   files. Update it at the start of every reviewer cycle (parallel Architect +
   Design Critic, then Evaluator). See "Round state file" below.

2. **Build identity.** On a new build, create `pipeline-state/builds/{ISO-timestamp}/`
   and point the symlink (or copy, if symlinks are unavailable on the host)
   `pipeline-state/current` to it. All round-scoped state lives under the
   current build's directory. Older builds are preserved for reference.

3. **Skip-unaffected-reviewers.** For revision rounds, inspect what changed and
   skip reviewers whose dimensions are not affected. See "Skip-unaffected-reviewers
   policy" below.

4. **Format-version checks.** Before passing one agent's output to the next,
   verify the `format-version:` header on the first line. On mismatch, halt
   with a clear error — do not let an agent parse a future format.

5. **Conflict resolution.** If a Generator revision pass writes `CONFLICT.md`,
   surface it to the user in the next status check. Do not silently merge
   contradictory reviewer findings.

6. **Escalation handling.** If any agent writes `ESCALATION_REQUESTED.md`, pause
   the build, surface the question to the user, capture their answer to
   `pipeline-state/user-intervention.md`, and resume. Do not consume a round.

7. **Mid-flight user intervention.** When the user issues "Pause build:
   [message]", append the message to `pipeline-state/user-intervention.md`
   with a timestamp. The next Generator pass reads and processes it.

8. **Cost tracking.** Append a per-round entry to `pipeline-state/cost.md`
   recording approximate tokens consumed. If the cost threshold is reached
   (default: **US$100 per build**, user-configurable; Fable 5 is $10/$50 per
   MTok — 2× Opus 4.8), halt and ask the user to confirm continuation.
   Also record any refusal/fallback events (agent, `stop_details.category`,
   retry model) — requests refused before any output are unbilled, and
   fallback credit refunds the prompt-cache cost of the model switch.

9. **Pipeline index.** Maintain `pipeline-state/index.md` — a 30-line at-a-glance
   summary of pipeline state (current round, last phase, current reviewer
   verdicts, last revision summary). Reading agents start here; deeper files
   are reference material.

10. **Retrospective.** The Evaluator writes `RETROSPECTIVE.md` on PASS or
    UNRECOVERABLE. Surface it to the user when the pipeline halts.

11. **Acceptance Score bookkeeping (computed, never hand-totaled).** After
    each Evaluator verdict, collect the `score-block` from each reviewer
    report, read any carried penalties from the prior `score-history.md` row
    (for reviewers skipped this round), assemble the JSON payload documented
    in `.claude/scripts/score.py`, and run that script. Paste its emitted row
    under the table in `pipeline-state/score-history.md` and put the headline
    Acceptance Score into `pipeline-state/index.md`. Do not compute the
    scalar yourself — the script is the deterministic source of truth.

12. **Scoreboard.** After each Evaluator verdict, append one row to
    `pipeline-state/scoreboard.md` classifying the round as Generator WIN
    (all reviewers PASS on first contact and score ≥ threshold),
    Discriminator WIN (any reviewer landed a finding forcing a revision), or
    Draw (CONDITIONAL PASS). The flaw-landed column names the highest-severity
    finding landed (or `none` on a Generator WIN).

13. **Attack-library harvesting.** On any reviewer FAIL, once the finding is
    confirmed real (not withdrawn via `CONFLICT.md` adjudication), distill it
    into a probe and append it to the matching dimension shard of
    `pipeline-state/attack-library.md` using that file's schema and
    append-only/dedup/retirement policy. The library persists across builds
    via the harvest-back protocol (Responsibility #17).

14. **False-positive accounting (honest auditor).** When `CONFLICT.md`
    adjudication (or a subsequent Evaluator round) withdraws a finding a
    reviewer raised, record it in that reviewer's `fp_withdrawn` count for the
    round the withdrawal is confirmed, so the `FalsePositivePenalty` is
    attributed to the reviewer that raised it. This is the counterweight that
    keeps the adversarial framing from rewarding spurious findings — a
    reviewer that over-reports loses score just as the Generator does.

15. **Refusal handling (Fable 5 safety classifiers).** `claude-fable-5` can
    decline a request with `stop_reason: "refusal"` (an HTTP 200, not an
    error) — benign security QA is the most likely trigger in this pipeline.
    If any sub-agent invocation ends in a refusal, log the
    `stop_details.category` (`cyber`, `bio`, `reasoning_extraction`, or
    null) to `pipeline-state/progress.md` and re-run that invocation on
    `claude-opus-4-8`. A refusal does not consume a round. Where the harness
    supports it, prefer the beta `fallbacks` parameter or the SDK
    refusal-fallback middleware over a manual retry (fallback credit refunds
    the prompt-cache cost of switching). The Evaluator's security probes are
    the most refusal-prone surface: attack-library probes marked
    `Refusal-risk: high` are run on `claude-opus-4-8` preemptively, and an
    Evaluator that records `SECURITY PROBES REFUSED` in
    `pipeline-state/checkpoint.md` gets its security-probe section re-run on
    `claude-opus-4-8` before the round's verdict stands. Note: Fable 5 also
    requires 30-day data retention and is unavailable under zero-data-retention
    arrangements (such requests 400 with `invalid_request_error`) — the
    `claude-opus-4-8` fallback path covers that failure mode too.

16. **Playbook harvesting (Generator memory).** After `RETROSPECTIVE.md` is
    written (PASS or UNRECOVERABLE), distill the build's transferable
    lessons — especially its "Persistent Failure Patterns" — into
    `pipeline-state/playbook.md` using that file's schema and
    append/dedup/retire policy. The playbook is the Generator's cross-build
    memory (the defensive mirror of the attack library) and is read by the
    Generator only — never pass it to a reviewer, so the discriminators'
    probe surface stays independent. Lessons return to the template via the
    harvest-back protocol (Responsibility #17).

17. **Harvest-back (cross-build memory return).** Builds run in per-build
    clones, so probes, lessons, and calibration data do not accumulate in
    the template by themselves. After Responsibilities #13 and #16 are
    complete (post-`RETROSPECTIVE.md`, on PASS **or** UNRECOVERABLE — failed
    builds usually teach the most), execute the Harvest-Back Protocol below:
    `.claude/scripts/harvest.sh` stages the template's latest `main` in a
    `.harvest/` worktree, the orchestrator merges this build's new
    attack-library probes, playbook lessons, and one `build-ledger.md` row
    into it, and the script commits, pushes a `harvest/<timestamp>` branch,
    and opens a PR against the template. The user's merge review is the
    dedup/quality backstop; the next clone inherits whatever merges.

## Resume Protocol

When invoked with "Resume build":

1. Read `pipeline-state/index.md` for the at-a-glance state.
2. Read `pipeline-state/round.md` for the current round number.
3. Read `pipeline-state/progress.md` to find the last completed phase / revision entry.
4. Read `pipeline-state/checkpoint.md` to find the last Evaluator round state.
5. Read `pipeline-state/architecture-checkpoint.md` to find the last Architect round state.
6. Read `pipeline-state/ux-checkpoint.md` to find the last Design Critic round state.
7. Read `pipeline-state/session.md` to find the last completed feature within the current Generator phase.
8. Read `pipeline-state/user-intervention.md` (if it exists) for any pending user input.
9. Determine re-entry point (check in this order):
   - If `ESCALATION_REQUESTED.md` exists and is unanswered: surface the question to the user; pause.
   - If `CONFLICT.md` exists and is unresolved: surface to the user; pause.
   - If Evaluator has a round IN PROGRESS: re-invoke the Evaluator.
   - If Evaluator returned CONDITIONAL PASS and the targeted fix is not yet logged: re-invoke the Generator with the eval report for the targeted fix.
   - If the Architect or Design Critic has a round IN PROGRESS: re-invoke whichever is in progress (they run concurrently; re-launch both in parallel if both are mid-round).
   - If one reviewer completed round N but the other never started (and is not skipped under the skip-unaffected policy): invoke the missing reviewer.
   - If either reviewer issued FAIL for round N but `REVISION COMPLETE — Round N` is absent from progress.md: re-invoke the Generator once, passing the path(s) of every failing report (`architecture_review_round_N.md` and/or `design_critique_round_N.md`) for a single combined revision pass.
   - If both reviewers completed round N (PASS, or FAIL with the combined revision logged) but the Evaluator has not yet run for that round: re-invoke the Evaluator.
   - If Generator is mid-phase (session.md shows incomplete phase): re-invoke the Generator, instructing it to read `pipeline-state/session.md` and continue from the last completed feature.
   - If a phase boundary was the last log entry in progress.md (HANDOFF COMPLETE not present): re-invoke the Generator at the next phase.
   - If only Planner has completed (plan.md is populated, progress.md is empty): re-invoke the Generator from Phase 1.
   - If only Clarifier has completed (clarifier_output.md exists, plan.md is absent or empty): re-invoke the Planner with the content of clarifier_output.md.
10. Continue the pipeline forward from that point.

## Round State File

At the start of every reviewer cycle (each fresh parallel Architect + Design
Critic launch), write `pipeline-state/round.md`:

```
Current Round: N
Started: [timestamp]
```

Sub-agents read this to determine the round number. They no longer count
review files themselves — the orchestrator's write is authoritative. This
removes a fragile counting-by-files dependency.

## Skip-Unaffected-Reviewers Policy

On revision rounds, before launching the reviewer batch, inspect the prior
combined revision's `Modified files:` list to decide which reviewers belong
in this round's parallel batch:

- **The revision touched only user-facing flows (UI copy, styling, ARIA,
  frontend behavior)** — the Architect's prior structural verdict is
  preserved; you may skip the Architect. Run Design Critic and Evaluator.
- **The revision touched only non-user-facing structure (data layer,
  module boundaries, naming) with no overlap with user-facing flows** —
  the Design Critic's prior verdict may still hold; you may skip the
  Design Critic. Run Architect and Evaluator.
- **The revision touched multiple layers** — run both reviewers
  (concurrently) and then the Evaluator.

Each reviewer agent also chooses delta vs. full mode internally based on the
prior revision's `Modified files:` list. The orchestrator's skip policy is the
outer cut; the agent's mode is the inner cut.

State the skip decision in the orchestrator's status message when launching
the batch. Conservative default: run every reviewer. Skip only when the
file-list evidence is unambiguous.

## Adversarial Game Mechanics

The pipeline is a minimax game over a single shared scalar. The Generator
maximizes the **Acceptance Score**; the discriminator agents (Architect,
Design Critic, Evaluator) minimize it by landing confirmed defects. The
scalar, the gate precedence, the threshold ratchet, and the per-reviewer
contributions are all defined in `pipeline-state/value-function.md` — the
canonical reference, which agents consume rather than re-deriving.

The arithmetic is computed by `.claude/scripts/score.py`, not by hand.
Reviewers emit COUNTS in a fenced `score-block`; the orchestrator assembles
them into one JSON payload and runs the script, which returns the
deterministic Acceptance Score, the threshold check, and a ready-to-append
history row. This keeps the headline number and the PASS-on-score gate
deterministic rather than model-estimated.

Gate precedence (from `value-function.md`): **(1)** Tier 1 failures are
absolute — no score rescues them; **(2)** if Tier 1 passes, the
Acceptance-Score ratchet (6.5 → 7.0 → 7.5) is the authoritative pass/fail;
**(3)** the old standalone Tier-2≥7 rule is subsumed as the `Tier2Quality`
component, not a parallel gate.

State files that realize the game:

- **`pipeline-state/value-function.md`** — canonical formula, gate
  precedence, and the machine-readable `score-block` schema.
- **`.claude/scripts/score.py`** — deterministic calculator; the only thing
  that does the multiplication and summation.
- **`pipeline-state/score-history.md`** — one row per round (per-reviewer
  penalties + novelty + false-positive columns). Also the carry-forward
  source of truth for skipped reviewers — read penalties from the prior row,
  never from memory.
- **`pipeline-state/scoreboard.md`** — one row per round, the
  Generator-vs-Discriminator outcome.
- **`pipeline-state/attack-library.md`** — sharded, cross-build probe
  library. Reviewers load only their dimension's shard and add a novel probe
  only when a genuinely new failure class surfaces (discovery-gated, not
  mandatory — a quota of filler probes would dilute every future round).

The orchestrator's responsibilities #11–#14 above own the writes. Reviewers
emit `score-block` counts and probe findings; the orchestrator runs the
script and composes the round totals.

## Harvest-Back Protocol (Cross-Build Memory)

Each build runs in its own clone of this template, so nothing accumulates in
the template by default. Three files are designed to compound across builds:
`pipeline-state/attack-library.md` (discriminator probes),
`pipeline-state/playbook.md` (Generator lessons), and
`pipeline-state/build-ledger.md` (one summary row per build — the substrate
for threshold recalibration). The harvest-back protocol returns a finished
build's deltas to the template as a reviewable PR.

**When:** after `RETROSPECTIVE.md` is written and Responsibilities #13
(attack-library harvesting) and #16 (playbook harvesting) have run in the
clone. Harvest UNRECOVERABLE builds too.

**Steps** (the script does the git plumbing; the orchestrator does the
content work between the two calls):

1. Run `.claude/scripts/harvest.sh begin`. It fetches `origin/main` and
   creates a `harvest/<timestamp>` branch in a `.harvest/` worktree — the
   template's latest state, untouched by this build's working tree.
2. Merge this build's **new** entries into the worktree's copies:
   - new probes → end of their shard in `.harvest/pipeline-state/attack-library.md`
   - new lessons → end of `.harvest/pipeline-state/playbook.md`
   - one build row → the table in `.harvest/pipeline-state/build-ledger.md`

   Dedup against the **fetched** versions, not this clone's snapshot — the
   template may have advanced since the clone was cut. A duplicate increments
   the existing entry's `Seen:` count instead of being re-added. Append-only,
   stable-first ordering, and the no-weakening/retirement rule (template
   author only) all apply.
3. Run `.claude/scripts/harvest.sh finish "<one-line build summary>"`. It
   verifies only the three harvestable files changed (anything else aborts —
   build artifacts never flow back to the template), commits, pushes, and
   opens the PR with a reviewer checklist.
4. The user reviews and merges. Merge review is the dedup/quality backstop:
   low-signal probes or lessons get cut there, before they tax every future
   build.

`.claude/scripts/harvest.sh abort` discards an in-progress harvest.

## Conflict and Escalation Handling

- **CONFLICT.md** — Generator writes this when two reviewer findings are
  directly contradictory and it cannot satisfy both. The orchestrator
  surfaces the conflict to the user and lets the Evaluator's next round
  adjudicate against the spec.
- **ESCALATION_REQUESTED.md** — Any agent writes this to request user input.
  The orchestrator pauses, surfaces the question, captures the answer to
  `pipeline-state/user-intervention.md`, and resumes. This does not consume
  a round.
- **user-intervention.md** — Append-only log of all mid-flight user input.
  Each entry is timestamped. The Generator reads new entries on every pass.

## Orchestration Steps

1. **Invoke the Clarifier sub-agent** with the user's concept.
   Capture its full output and write it to `clarifier_output.md` in the project root.

2. **Invoke the Planner sub-agent** with the content of `clarifier_output.md` as its
   input prompt. Capture its full output and write it to BOTH:
   - `pipeline-state/plan.md` (canonical record)
   - `planner_output.md` (project root, for agent compatibility)

3. **Invoke the Generator sub-agent.**
   It reads `planner_output.md`, builds the app into `output/`, and writes
   `HANDOFF.md`, `BUILD_NOTES.md`, and `VERIFY_NOTES.md` to the project root
   when done.

   Write `pipeline-state/round.md` with `Current Round: 1` immediately before
   the first reviewer cycle.

4. **Invoke the Architect and Design Critic sub-agents concurrently.**
   They are independent — launch both in parallel (subject to the
   skip-unaffected-reviewers policy on revision rounds):

   - The **Architect** reads `planner_output.md`, `HANDOFF.md`, `BUILD_NOTES.md`,
     and the source code in `output/`, and reviews the codebase for structural
     quality across six dimensions (naming consistency, separation of concerns,
     coupling, pattern coherence, scalability, security boundaries). It writes
     `architecture_review_round_N.md` (always, regardless of verdict).
   - The **Design Critic** reads `planner_output.md` and `HANDOFF.md`, starts
     the app, and reviews it for usability and accessibility across ten
     dimensions plus i18n probe, at three viewport sizes. It does **not** read
     the Architect's review — the two run concurrently. It writes
     `design_critique_round_N.md` (always, regardless of verdict).

   When both have completed:
   - **If either verdict is FAIL:** Re-invoke the Generator **once**, passing
     the explicit path(s) of every failing report
     (`architecture_review_round_N.md` and/or `design_critique_round_N.md`).
     The Generator reads all provided reports and makes one **combined
     revision pass**, then appends
     `REVISION COMPLETE — Round N — [timestamp]` plus the `Modified files:`
     and `Pattern Deviations:` lists to `pipeline-state/progress.md`.
     Then proceed to Step 5.
   - **If both PASS:** Proceed directly to Step 5.

5. **Invoke the Evaluator sub-agent.**
   It reads `planner_output.md`, `HANDOFF.md`, `VERIFY_NOTES.md`,
   `architecture_review_round_N.md`, and `design_critique_round_N.md`, starts
   the app, and tests it for functional correctness, spec compliance, and
   security baseline.
   - On FAIL: it writes `eval_report_round_N.md`. Increment N in
     `pipeline-state/round.md`. Re-invoke the Generator, passing the explicit
     path `eval_report_round_N.md`. The Generator must read that file before
     beginning its revision. Repeat from Step 4 (launch the reviewer batch,
     applying the skip-unaffected policy).
   - On CONDITIONAL PASS: it writes `eval_report_round_N.md` with verdict
     `CONDITIONAL PASS`. Re-invoke the Generator for a single targeted fix
     pass (not a full revision round). Re-invoke the Evaluator only against
     the conditional criterion. On success, proceed to PASS. On failure,
     downgrade to FAIL and continue normally.
   - On PASS: it writes `EVAL_PASS.md` and `RETROSPECTIVE.md`. Pipeline is
     complete.
   - After 5 failed rounds: Evaluator writes `EVAL_UNRECOVERABLE.md` and
     `RETROSPECTIVE.md`. Stop.

## File Conventions
| File | Written by | Read by |
|---|---|---|
| `clarifier_output.md` | Orchestrator (from Clarifier output) | Planner |
| `planner_output.md` | Orchestrator (from Planner output) | Generator, Architect, Design Critic, Evaluator |
| `pipeline-state/plan.md` | Orchestrator (canonical copy) | — |
| `output/` | Generator | Architect, Design Critic, Evaluator |
| `HANDOFF.md` | Generator | Architect, Design Critic, Evaluator |
| `BUILD_NOTES.md` | Generator | Architect, Evaluator |
| `VERIFY_NOTES.md` | Generator | Evaluator |
| `architecture_review_round_N.md` | Architect | Generator (combined revision), Evaluator |
| `design_critique_round_N.md` | Design Critic | Generator (combined revision), Evaluator |
| `eval_report_round_N.md` | Evaluator | Generator (next round) |
| `EVAL_PASS.md` | Evaluator | Orchestrator |
| `EVAL_UNRECOVERABLE.md` | Evaluator | Orchestrator |
| `RETROSPECTIVE.md` | Evaluator | Orchestrator (surfaces to user) |
| `ESCALATION_REQUESTED.md` | Any agent | Orchestrator → User |
| `CONFLICT.md` | Generator | Orchestrator → Evaluator (next round) |
| `pipeline-state/round.md` | Orchestrator | All reviewer agents |
| `pipeline-state/index.md` | Orchestrator | All agents (at-a-glance state) |
| `pipeline-state/progress.md` | Generator (phase transitions + combined revisions, with Modified files lists) | Orchestrator, Architect, Design Critic |
| `pipeline-state/checkpoint.md` | Evaluator (round state, conditional-pass flag) | Orchestrator |
| `pipeline-state/architecture-checkpoint.md` | Architect (round state) | Orchestrator |
| `pipeline-state/ux-checkpoint.md` | Design Critic (round state) | Orchestrator |
| `pipeline-state/session.md` | Generator (per-feature progress) | Orchestrator (resume) |
| `pipeline-state/user-intervention.md` | Orchestrator (from "Pause build" or escalation answers) | Generator |
| `pipeline-state/cost.md` | Orchestrator (per-round token usage) | Orchestrator |
| `pipeline-state/value-function.md` | Template (canonical) | All reviewer agents, Generator |
| `pipeline-state/score-history.md` | Orchestrator (per-round breakdown + carry-forward source) | Orchestrator, Generator |
| `pipeline-state/scoreboard.md` | Orchestrator (per-round Generator-vs-Discriminator outcome) | Orchestrator, user |
| `pipeline-state/attack-library.md` | Orchestrator (appends confirmed defects) + reviewer agents (append novel probes to their shard) | All reviewer agents (own shard only) |
| `pipeline-state/playbook.md` | Orchestrator (post-build lesson harvesting) | Generator only (never reviewers) |
| `pipeline-state/build-ledger.md` | Orchestrator (one row per build, via harvest PR) | Orchestrator, user (threshold calibration) |
| `.claude/scripts/score.py` | Template (canonical calculator) | Orchestrator (runs each round) |
| `.claude/scripts/harvest.sh` | Template (canonical plumbing) | Orchestrator (runs post-RETROSPECTIVE) |
| `pipeline-state/builds/{timestamp}/` | Orchestrator (per-build dir) | Orchestrator |
| `pipeline-state/current` | Orchestrator (symlink or pointer to active build) | All agents |

## Format-Version Headers

Every handoff file begins with a `format-version:` line. Reading agents
check it and surface a clear error on mismatch rather than parsing garbage.

| File | Current version |
|---|---|
| `planner_output.md` | `planner-v1` |
| `HANDOFF.md` | `handoff-v1` |
| `BUILD_NOTES.md` | `build-notes-v1` |
| `VERIFY_NOTES.md` | `verify-notes-v1` |
| `architecture_review_round_N.md` | `architecture-review-v1` |
| `design_critique_round_N.md` | `design-critique-v1` |
| `eval_report_round_N.md` | `eval-report-v1` |
| `EVAL_PASS.md` | `eval-pass-v1` |
| `EVAL_UNRECOVERABLE.md` | `eval-unrecoverable-v1` |
| `RETROSPECTIVE.md` | `retrospective-v1` |
| `ESCALATION_REQUESTED.md` | `escalation-v1` |
| `pipeline-state/value-function.md` | `value-function-v2` |
| `pipeline-state/score-history.md` | `score-history-v2` |
| `pipeline-state/scoreboard.md` | `scoreboard-v1` |
| `pipeline-state/attack-library.md` | `attack-library-v2` |
| `pipeline-state/playbook.md` | `playbook-v1` |
| `pipeline-state/build-ledger.md` | `build-ledger-v1` |

## Sub-Agent Locations
- `.claude/agents/clarifier.md`
- `.claude/agents/planner.md`
- `.claude/agents/generator.md`
- `.claude/agents/architect.md`
- `.claude/agents/design-critic.md`
- `.claude/agents/evaluator.md`
