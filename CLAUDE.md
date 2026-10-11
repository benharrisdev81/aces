# Autonomous Build Pipeline

## Pipeline Overview
Seven sub-agents: Clarifier → Planner → Generator → (Architect ∥ Design Critic → Security Prober → Evaluator).
Each round starts with one Generator pass (the initial build, or one combined revision) that
commits to `output/`. Every reviewer then reviews that same commit. The Architect reads only
the code and runs in parallel with the **live-app chain**: the Design Critic, then the Security
Prober, then the Evaluator, one after another, each starting and stopping its own app
instance. Every report records the commit it reviewed. The orchestrator then runs
`.claude/scripts/gate.py`, which alone decides PASS or FAIL from the four reports. On FAIL,
the next round's Generator pass addresses every report with open findings. The cap is 5
rounds, and Round 5 is reviewed and gated like any other. A Fable build that fails 5
consecutive rounds almost certainly has a spec problem (escalation territory), not a
generation problem.

The pipeline is structured as an **adversarial game**: the Generator tries to
pass the ship gate (defined in `pipeline-state/ship-gate.md`), and the
Architect, Design Critic, Security Prober, and Evaluator try to land
confirmed defects that fail it. Confirmed defects are harvested into
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

Fable turns on hard tasks run for many minutes at `high` effort, and a
full build can extend for hours. Do not treat a long-running sub-agent turn
as hung — `.claude/settings.json` raises bash and MCP tool timeouts, and the
per-feature `session.md` checkpoint plus the Resume Protocol make
interruption cheap. Check on a running build asynchronously (status checks
between agent invocations) rather than blocking on it; never inject
remaining-token or budget countdowns into a sub-agent's prompt — Fable may
wrap up prematurely when shown one (cost accounting stays orchestrator-side
in `cost.md`).

## Model and Effort Tiering

Each sub-agent pins `model:` and `effort:` in its frontmatter; the table below
mirrors those values.

| Agent | `model` | `effort` | Tools (frontmatter) |
|---|---|---|---|
| Clarifier | `opus` | `high` | `tools: Write` |
| Planner | `fable` | `high` | `tools: Write` |
| Generator | `fable` | `high` | `disallowedTools: Agent` |
| Architect | `opus` (trial, see O2) | `high` | `tools: Read, Grep, Glob, Bash, Write` |
| Design Critic | `fable` | `high` | `tools: Read, Bash, Write, mcp__playwright` |
| Security Prober | `opus` | `high` | `tools: Read, Bash, Write, mcp__playwright` |
| Evaluator | `fable` | `high` | `tools: Read, Grep, Glob, Bash, Write, mcp__playwright` |

## How to Run the Pipeline
- **Start a new build:** "Build [product concept]"
- **Resume an interrupted build:** "Resume build" — reads `pipeline-state/`
  files to determine where the pipeline was interrupted, then re-invokes the
  appropriate sub-agent.
- **Pause and add mid-flight input:** "Pause build: [feedback / change /
  question]" — appends the user's message to `planner_output.md` as a spec
  amendment (Responsibility #7). Use sparingly; mid-flight changes invalidate
  work already done.

## Orchestrator Responsibilities

The orchestrator (this top-level Claude Code session) owns these jobs that no
single sub-agent can:

1. **Round state.** Maintain `pipeline-state/round.md` as the single source of
   truth for the current round number; sub-agents read it instead of counting
   files. Update it at the start of every round, before the Generator pass.
   See "Round state file" below.

2. **One build per clone.** Each build runs in its own clone, so build state
   lives in the project root and directly in `pipeline-state/`. Do not create
   per-build subdirectories or pointers.

3. **Every reviewer, every round.** Run all four reviewers in every round;
   never skip one. The gate needs all four reports on the same commit. A
   reviewer whose area a revision barely touched stays cheap by choosing
   delta mode itself, based on the round's `REVISION COMPLETE` record.

4. **Format-version checks.** Before passing one agent's output to the next,
   verify the `format-version:` header on the first line. On mismatch, halt
   with a clear error — do not let an agent parse a future format.

5. **Conflict resolution.** If a Generator revision pass writes `CONFLICT.md`,
   surface it to the user in the next status check. Do not silently merge
   contradictory reviewer findings.

6. **Escalation handling.** If any agent writes `ESCALATION_REQUESTED.md`, pause
   the build, surface the question to the user, record their answer as a
   spec amendment (#7), and resume. Do not consume a round.

7. **Spec amendments.** When the user issues "Pause build: [message]" or
   answers an escalation, append to the end of `planner_output.md`:

   ```
   <spec_amendment id="A[n]" date="[timestamp]">
   [the user's words, verbatim]
   </spec_amendment>
   ```

   Every agent reads `planner_output.md`, so every agent sees it; a later
   amendment wins over anything earlier. Also append the same text with a
   timestamp to `pipeline-state/user-intervention.md`, which is a raw log
   only and no agent reads.

8. **Cost tracking.** Append a per-round entry to `pipeline-state/cost.md`
   recording approximate tokens consumed. If the cost threshold is reached
   (default: **US$100 per build**, user-configurable), halt and ask the user to
   confirm continuation.

9. **Pipeline index.** Maintain `pipeline-state/index.md` — a 30-line at-a-glance
   summary of pipeline state (current round, last phase, latest gate
   result, last revision summary). Reading agents start here; deeper files
   are reference material.

10. **Retrospective.** After you write `EVAL_PASS.md` or
    `EVAL_UNRECOVERABLE.md`, invoke the Evaluator once with
    `mode: retrospective`; it writes `RETROSPECTIVE.md`. Surface it to the
    user when the pipeline halts.

11. **Ship gate (computed, never judged).** When all four reports for round
    N exist, run `python3 .claude/scripts/gate.py N --tier <tier>`, taking
    `<tier>` from the `<originality_tier>` section of `planner_output.md`.
    The script reads the reports' score-blocks itself; its exit code alone
    decides the round (see Orchestration Step 5). Put its `Round N:` result
    line into `pipeline-state/index.md`. Never decide PASS or FAIL yourself,
    and never edit a report's score-block.

12. **Terminal files.** Only you write `EVAL_PASS.md` and
    `EVAL_UNRECOVERABLE.md`, and only from `gate.py` output: `EVAL_PASS.md`
    after exit 0, `EVAL_UNRECOVERABLE.md` after exit 1 in Round 5. Start each
    with its format-version line (`eval-pass-v1` or
    `eval-unrecoverable-v1`). Include the round number, the commit, the
    gate's full output, and a short summary drawn from that round's reports:
    what the build does well for a PASS, or every finding still open in the
    Round 5 reports for UNRECOVERABLE.

13. **Attack-library harvesting.** You are the only writer of
    `pipeline-state/attack-library.md`; reviewers never edit it. After the
    build ends (gate PASS or Round 5 FAIL; for a user-override build, see
    #14), read the `## Proposed Probes` section of every round's reports. Keep
    a proposal only if its source finding was real: fixed in a later round, or
    still open at the end. Append each kept probe to the end of its shard,
    using that file's schema and append-only/dedup/retirement policy; a
    duplicate increments the existing probe's `Seen:` count. The library
    persists across builds via the harvest-back protocol (Responsibility #17).

14. **User-override acceptance.** If the user accepts a build the gate
    failed, write `EVAL_PASS.md` per #12, with the line
    `**Accepted by user override**` under its header, the failing gate
    output, and the user's words verbatim. Then run the retrospective (#10).
    Do not run harvesting (#13, #16, #17) automatically. Ask the user
    separately whether to harvest this build, and run it only on an explicit
    yes. Never bundle the harvest into the acceptance question.

15. **Missing reports.** If a subagent returns no report file, re-invoke it
    once with `model: opus`; if that also fails, write
    `ESCALATION_REQUESTED.md`. A re-invocation does not consume a round.

16. **Playbook harvesting (Generator memory).** After `RETROSPECTIVE.md` is
    written following a gate PASS or a Round 5 FAIL (for a user-override
    build, see #14), distill the build's transferable
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
    builds usually teach the most; for a user-override build, see #14),
    execute the Harvest-Back Protocol below:
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
6b. Read `pipeline-state/security-checkpoint.md` to find the last Security Prober round state.
7. Read `pipeline-state/session.md` to find the last completed feature within the current Generator phase.
8. Read the `<spec_amendment>` blocks at the end of `planner_output.md`, if any.
9. Determine re-entry point (check in this order):
   - If `ESCALATION_REQUESTED.md` exists and is unanswered: surface the question to the user; pause.
   - If `CONFLICT.md` exists and is unresolved: surface to the user; pause.
   - If round.md shows Round N > 1 and progress.md has no `REVISION COMPLETE` record for Round N: re-invoke the Generator for the combined revision, passing every Round N-1 report with open findings.
   - The remaining reviewer branches apply only once the round's Generator pass is complete (`HANDOFF COMPLETE` for Round 1, the `REVISION COMPLETE` record for Round N > 1):
     - If any reviewer has round N IN PROGRESS in its checkpoint file: re-invoke it. If it belongs to the live-app chain, continue the chain after it.
     - If `architecture_review_round_N.md` is missing: invoke the Architect.
     - If any live-app chain report for round N is missing (`design_critique_round_N.md`, `security_probe_round_N.md`, `eval_report_round_N.md`): invoke the first missing agent in chain order (Design Critic, Security Prober, Evaluator) and continue the chain from there. This can run in parallel with the Architect branch above.
     - If all four round N reports exist and neither `EVAL_PASS.md` nor `EVAL_UNRECOVERABLE.md` exists: run the gate (Orchestration Step 5). The gate is deterministic, so re-running it is safe.
   - If `EVAL_PASS.md` or `EVAL_UNRECOVERABLE.md` exists but `RETROSPECTIVE.md` does not: invoke the Evaluator with `mode: retrospective`.
   - If `RETROSPECTIVE.md` exists: the build is finished. Ask the user whether harvesting (#13, #16, #17) already ran before running it.
   - If Generator is mid-phase (session.md shows incomplete phase): re-invoke the Generator, instructing it to read `pipeline-state/session.md` and continue from the last completed feature.
   - If a phase boundary was the last log entry in progress.md (HANDOFF COMPLETE not present): re-invoke the Generator at the next phase.
   - If only Planner has completed (planner_output.md is populated, progress.md is empty): re-invoke the Generator from Phase 1.
   - If only Clarifier has completed (clarifier_output.md exists, planner_output.md is absent or empty): re-invoke the Planner with the content of clarifier_output.md.
10. Continue the pipeline forward from that point.

## Round State File

At the start of every round, before that round's Generator pass, write
`pipeline-state/round.md`:

```
Current Round: N
Started: [timestamp]
```

Sub-agents read this to determine the round number. They no longer count
review files themselves — the orchestrator's write is authoritative. This
removes a fragile counting-by-files dependency.

## Adversarial Game Mechanics

The Generator tries to pass the ship gate; the four reviewers try to land
confirmed defects that fail it. `pipeline-state/ship-gate.md` defines the
gate's pass conditions and the exact score-block schema. It is the
human-readable mirror of `.claude/scripts/gate.py`, which is the source of
truth; change both together.

Each reviewer emits one fenced `score-block` of counts and subscores, stamped
with the commit it reviewed. `gate.py` reads the four reports directly,
returns INVALID on a malformed block or a commit mismatch, and otherwise
checks every pass condition against that one commit. Nothing is averaged,
the floors never tighten between rounds, and nothing carries over. The gate
also prints an `open_defect_load` statistic that never affects the result.

State files that realize the game:

- **`pipeline-state/ship-gate.md`**: the pass conditions and the score-block
  schema, in plain language.
- **`.claude/scripts/gate.py`**: the deterministic gate, tested by
  `.claude/scripts/tests/test_gate.py`.
- **`pipeline-state/attack-library.md`** — sharded, cross-build probe
  library. Reviewers load only their dimension's shard and propose a probe
  in their report only when a genuinely new failure class surfaces
  (discovery-gated, not mandatory); the orchestrator alone appends (#13).

Responsibilities #11 to #14 above own the gate run, the terminal files, and
the library writes. Reviewers write only their own reports.

## Harvest-Back Protocol (Cross-Build Memory)

Each build runs in its own clone of this template, so nothing accumulates in
the template by default. Three files are designed to compound across builds:
`pipeline-state/attack-library.md` (discriminator probes),
`pipeline-state/playbook.md` (Generator lessons), and
`pipeline-state/build-ledger.md` (one summary row per build, the substrate
for gate calibration). The harvest-back protocol returns a finished
build's deltas to the template as a reviewable PR.

**When:** after `RETROSPECTIVE.md` is written and Responsibilities #13
(attack-library harvesting) and #16 (playbook harvesting) have run in the
clone. Harvest UNRECOVERABLE builds too. Harvest a user-override build only
when the user explicitly asks (Responsibility #14).

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
  The orchestrator pauses, surfaces the question, records the answer as a
  spec amendment (#7), and resumes. This does not consume a round.
- **user-intervention.md** — Append-only raw log of all mid-flight user
  input. No agent reads it; amendments reach agents through
  `planner_output.md`.

## Orchestration Steps

1. **Clarify.**
   a. Invoke the Clarifier with `mode: questions` and the user's concept. It returns
      either `NO_QUESTIONS` or a `<clarifier_questions>` block (max 5, numbered).
   b. If it returned questions, ask them yourself with AskUserQuestion (or in plain
      text if more than 4) and collect the answers verbatim.
   c. Invoke the Clarifier again with `mode: report`, the concept, its own questions,
      and the user's verbatim answers. It writes `clarifier_output.md` itself.
   d. Confirm `clarifier_output.md` exists and line 1 is `<clarification_report>`.

2. **Invoke the Planner sub-agent** with the content of `clarifier_output.md` as its
   input prompt. It writes `planner_output.md` itself; this is the only copy of
   the spec. Confirm the file exists and line 1 is `format-version: planner-v1`.

   If either check in steps 1d or 2 fails, re-invoke that agent once and state the
   problem. If it fails again, write `ESCALATION_REQUESTED.md`.

3. **Start Round 1.** Write `pipeline-state/round.md` with `Current Round: 1`,
   then invoke the Generator sub-agent for the initial build. It reads
   `planner_output.md`, builds the app into `output/`, commits, and writes
   `HANDOFF.md`, `BUILD_NOTES.md`, and `VERIFY_NOTES.md` to the project root.

   If `planner_output.md` contains a `<runtime_secrets>` section, confirm
   every listed environment variable is set before any reviewer starts the
   app. If one is missing, pause the build and ask the user to set it.

4. **Review the commit.** When the round's Generator pass is complete, launch
   two tracks in parallel:

   a. The **Architect** reads `planner_output.md`, `HANDOFF.md`,
      `BUILD_NOTES.md`, and the source code in `output/`, reviews structural
      quality across six dimensions (naming consistency, separation of
      concerns, coupling, pattern coherence, scalability, security
      boundaries), and writes `architecture_review_round_N.md`. It never
      starts the app.
   b. The **live-app chain**, one agent after another, never in parallel.
      Each agent starts the app, tests it, and stops it before writing its
      report.
      1. The **Design Critic** reviews usability and accessibility across
         ten dimensions plus the i18n probe, at three viewport sizes, and
         writes `design_critique_round_N.md`.
      2. The **Security Prober** runs the built-in security probes and the
         attack library's Security shard, and writes
         `security_probe_round_N.md`.
      3. The **Evaluator** tests functional correctness and spec compliance,
         grades the Security Prober's results as its security baseline, and
         writes `eval_report_round_N.md`. It runs no security probes.

   Each reviewer reads `git -C output rev-parse --short=12 HEAD` before it
   starts reviewing and records that value as `commit:` in its report's
   score-block. Nothing commits to `output/` while reviewers run, so all four
   reports describe the same commit.

5. **Run the ship gate.** When all four reports exist, run:

   ```
   python3 .claude/scripts/gate.py N --tier <originality_tier from planner_output.md>
   ```

   - **Exit 0, PASS:** write `EVAL_PASS.md` (#12), then invoke the Evaluator with
     `mode: retrospective` to write `RETROSPECTIVE.md`. Then run
     attack-library harvesting (#13), playbook harvesting (#16), and
     harvest-back (#17). The pipeline is complete.
   - **Exit 1, FAIL, N < 5:** write `pipeline-state/round.md` with
     `Current Round: N+1`. Invoke the Generator once, passing the explicit
     path of every Round N report with open findings, for one combined
     revision pass. When its `REVISION COMPLETE` record appears in
     `pipeline-state/progress.md`, repeat from Step 4 for Round N+1.
   - **Exit 1, FAIL, N = 5:** write `EVAL_UNRECOVERABLE.md` (#12), then run
     the retrospective and harvest steps as on PASS. Stop.
   - **Exit 2, INVALID:** the gate's output names the offending report.
     Re-invoke that reviewer once for the same round, then rerun the gate.
     If it is still INVALID, write `ESCALATION_REQUESTED.md`.

   If the user accepts a build the gate failed, follow Responsibility #14.

## File Conventions
| File | Written by | Read by |
|---|---|---|
| `clarifier_output.md` | Clarifier (`mode: report`) | Planner |
| `planner_output.md` | Planner (orchestrator appends `<spec_amendment>` blocks) | Generator, Architect, Design Critic, Security Prober, Evaluator |
| `output/` | Generator | Architect, Design Critic, Security Prober, Evaluator |
| `HANDOFF.md` | Generator | Architect, Design Critic, Security Prober, Evaluator |
| `BUILD_NOTES.md` | Generator | Architect, Evaluator |
| `VERIFY_NOTES.md` | Generator | Evaluator |
| `architecture_review_round_N.md` | Architect | `gate.py`, Generator (next round) |
| `design_critique_round_N.md` | Design Critic | `gate.py`, Evaluator, Generator (next round) |
| `security_probe_round_N.md` | Security Prober | `gate.py`, Evaluator, Generator (next round) |
| `eval_report_round_N.md` | Evaluator | `gate.py`, Generator (next round) |
| `EVAL_PASS.md` | Orchestrator (from `gate.py` output, or a user override) | Evaluator (`mode: retrospective`), user |
| `EVAL_UNRECOVERABLE.md` | Orchestrator (from `gate.py` output) | Evaluator (`mode: retrospective`), user |
| `RETROSPECTIVE.md` | Evaluator (`mode: retrospective`) | Orchestrator (surfaces to user) |
| `ESCALATION_REQUESTED.md` | Any agent | Orchestrator → User |
| `CONFLICT.md` | Generator | Orchestrator → Evaluator (next round) |
| `pipeline-state/round.md` | Orchestrator | All reviewer agents |
| `pipeline-state/index.md` | Orchestrator | All agents (at-a-glance state) |
| `pipeline-state/progress.md` | Generator (phase transitions + one `REVISION COMPLETE` record per revision pass) | Orchestrator, Architect, Design Critic |
| `pipeline-state/checkpoint.md` | Evaluator (round state) | Orchestrator |
| `pipeline-state/architecture-checkpoint.md` | Architect (round state) | Orchestrator |
| `pipeline-state/ux-checkpoint.md` | Design Critic (round state) | Orchestrator |
| `pipeline-state/security-checkpoint.md` | Security Prober (round state) | Orchestrator |
| `pipeline-state/session.md` | Generator (per-feature progress) | Orchestrator (resume) |
| `pipeline-state/user-intervention.md` | Orchestrator (raw log of "Pause build" messages and escalation answers) | User only |
| `pipeline-state/cost.md` | Orchestrator (per-round token usage) | Orchestrator |
| `pipeline-state/ship-gate.md` | Template (mirror of `gate.py`) | Orchestrator, user |
| `pipeline-state/attack-library.md` | Orchestrator only (appends reviewers' Proposed Probes after the build, #13) | Architect, Design Critic, Security Prober (own shard only) |
| `pipeline-state/playbook.md` | Orchestrator (post-build lesson harvesting) | Generator only (never reviewers) |
| `pipeline-state/build-ledger.md` | Orchestrator (one row per build, via harvest PR) | Orchestrator, user (gate calibration) |
| `.claude/scripts/gate.py` | Template (canonical gate) | Orchestrator (runs each round) |
| `.claude/scripts/harvest.sh` | Template (canonical plumbing) | Orchestrator (runs post-RETROSPECTIVE) |

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
| `security_probe_round_N.md` | `security-probe-v1` |
| `eval_report_round_N.md` | `eval-report-v1` |
| `EVAL_PASS.md` | `eval-pass-v1` |
| `EVAL_UNRECOVERABLE.md` | `eval-unrecoverable-v1` |
| `RETROSPECTIVE.md` | `retrospective-v1` |
| `ESCALATION_REQUESTED.md` | `escalation-v1` |
| `pipeline-state/ship-gate.md` | `ship-gate-v1` |
| `pipeline-state/attack-library.md` | `attack-library-v2` |
| `pipeline-state/playbook.md` | `playbook-v1` |
| `pipeline-state/build-ledger.md` | `build-ledger-v1` |

## Sub-Agent Locations
- `.claude/agents/clarifier.md`
- `.claude/agents/planner.md`
- `.claude/agents/generator.md`
- `.claude/agents/architect.md`
- `.claude/agents/design-critic.md`
- `.claude/agents/security-prober.md`
- `.claude/agents/evaluator.md`
