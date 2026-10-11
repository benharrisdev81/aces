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

1. **Round state.** Start every round with `state.py round N`, before that
   round's Generator pass. It records the round in `state.json` and rewrites
   `pipeline-state/round.md`, which sub-agents read instead of counting
   files. See "Round state file" below.

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

5. **Conflict resolution.** The Generator records findings it cannot act on
   in `conflicts/round_N.md`, and the Evaluator adjudicates them in the same
   round. Do not pause for an `open`, `upheld`, or `withdrawn` entry. Pause
   and ask the user only about an entry marked `needs-user`, and record the
   answer as a spec amendment (#7).

6. **Escalation handling.** If any agent writes `ESCALATION_REQUESTED.md`, record
   it with `state.py set escalation '<agent and question>'`, pause the build,
   surface the question to the user, clear it with
   `state.py set escalation null` once answered, record their answer as a
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

8. **Build limits.** Before every Generator invocation, including a resume,
   run `state.py incr generator_invocations`. For every agent invocation,
   append one line to `pipeline-state/cost.md` with the agent, the round, and
   its start and end times. Pause and ask the user to confirm continuing when
   either limit is reached (both user-configurable):
   - **8 Generator invocations** per build
   - **6 hours** of wall-clock time since `build_started` in `state.json`

   You cannot measure tokens or dollars from inside the session, so do not
   estimate them. The user reads real spend from their billing or usage
   reporting after the build.

9. **Pipeline state.** `pipeline-state/state.json` records the round, the
   current step, that step's `pending` and `done` tasks, the commit under
   review, and any open escalation. Change it only through
   `python3 .claude/scripts/state.py`; never edit the JSON by hand. Before
   each Orchestration Step, run `state.py step <name> <task> ...` with the
   step's tasks; after each task succeeds, run `state.py done <task>`.

10. **Retrospective.** After you write `EVAL_PASS.md` or
    `EVAL_UNRECOVERABLE.md`, invoke the Evaluator once with
    `mode: retrospective`; it writes `RETROSPECTIVE.md`. Surface it to the
    user when the pipeline halts.

11. **Ship gate (computed, never judged).** When all four reports for round
    N exist, run `python3 .claude/scripts/gate.py N --tier <tier>`, taking
    `<tier>` from the `<originality_tier>` section of `planner_output.md`.
    The script reads the reports' score-blocks itself; its exit code alone
    decides the round (see Orchestration Step 5). Record its `Round N:`
    result line with `state.py set last_gate '<line>'`. Never decide PASS or
    FAIL yourself, and never edit a report's score-block.

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

1. Run `python3 .claude/scripts/state.py get`.
2. If `escalation` is set: surface the question to the user and pause.
3. If a `conflicts/round_*.md` entry is marked `needs-user` and no spec
   amendment answers it: surface it to the user and pause.
4. Re-run every task in `pending` for the current `step` and `round`:
   re-invoke each pending agent (chain agents in chain order, the Architect
   in parallel), rerun the gate, or redo the pending harvest task. A
   re-invoked Generator reads `pipeline-state/session.md` and continues from
   the last completed feature.
5. Continue the pipeline forward from that step.

Resume never infers state from the other files. `progress.md`, `session.md`,
and the per-agent checkpoint files (`checkpoint.md`,
`architecture-checkpoint.md`, `ux-checkpoint.md`, `security-checkpoint.md`)
are audit logs.

## Round State File

At the start of every round, before that round's Generator pass,
`state.py round N` writes `pipeline-state/round.md`:

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

- **`conflicts/round_N.md`**: the Generator adds one entry per finding it
  cannot act on, as a `contradiction` (two findings that cannot both be
  satisfied) or a `dispute` (evidence that a finding is wrong against the
  spec). The Evaluator adjudicates each entry in the same round as `upheld`,
  `withdrawn`, or `needs-user`. Reviewers never re-file a `withdrawn`
  finding. The orchestrator pauses only for `needs-user`.
- **ESCALATION_REQUESTED.md** — Any agent writes this to request user input.
  The orchestrator pauses, surfaces the question, records the answer as a
  spec amendment (#7), and resumes. This does not consume a round.
- **user-intervention.md** — Append-only raw log of all mid-flight user
  input. No agent reads it; amendments reach agents through
  `planner_output.md`.

## Orchestration Steps

Each step names its `state.py` step and tasks. Run `state.py step` before
the step and `state.py done <task>` after each task (Responsibility #9).

1. **Clarify.** First run `state.py init`. Step `clarify`, task `clarifier`.
   a. Invoke the Clarifier with `mode: questions` and the user's concept. It returns
      either `NO_QUESTIONS` or a `<clarifier_questions>` block (max 5, numbered).
   b. If it returned questions, ask them yourself with AskUserQuestion (or in plain
      text if more than 4) and collect the answers verbatim.
   c. Invoke the Clarifier again with `mode: report`, the concept, its own questions,
      and the user's verbatim answers. It writes `clarifier_output.md` itself.
   d. Confirm `clarifier_output.md` exists and line 1 is `<clarification_report>`.

2. **Invoke the Planner sub-agent** (step `plan`, task `planner`) with the
   content of `clarifier_output.md` as its input prompt. It writes
   `planner_output.md` itself; this is the only copy of the spec. Confirm the
   file exists and line 1 is `format-version: planner-v1`.

   If either check in steps 1d or 2 fails, re-invoke that agent once and state the
   problem. If it fails again, write `ESCALATION_REQUESTED.md`.

3. **Start Round 1.** Run `state.py round 1`, then invoke the Generator
   sub-agent for the initial build (step `build`, task `generator`). It reads
   `planner_output.md`, builds the app into `output/`, commits, and writes
   `HANDOFF.md`, `BUILD_NOTES.md`, and `VERIFY_NOTES.md` to the project root.

   If `planner_output.md` contains a `<runtime_secrets>` section, confirm
   every listed environment variable is set before any reviewer starts the
   app. If one is missing, pause the build and ask the user to set it.

4. **Review the commit.** When the round's Generator pass is complete, record
   the commit with `state.py set commit <output/ HEAD>` and launch two tracks
   in parallel (step `review`, tasks `architect design_critic security_prober
   evaluator`):

   a. The **Architect** reads `planner_output.md`, `HANDOFF.md`,
      `BUILD_NOTES.md`, and the source code in `output/`, reviews structural
      quality across six dimensions (naming consistency, separation of
      concerns, coupling, pattern coherence, scalability, security
      boundaries), and writes `architecture_review_round_N.md`. It never
      starts the app.
   b. The **live-app chain**, one agent after another, never in parallel.
      Each agent starts the app, tests it, and stops it before writing its
      report. Before launching each agent, free the app's ports: run the
      How to Stop commands in `HANDOFF.md`, then
      `lsof -ti :<port> | xargs kill` for each port it lists.
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

5. **Run the ship gate** (step `gate`, task `gate`). When all four reports
   exist, run:

   ```
   python3 .claude/scripts/gate.py N --tier <originality_tier from planner_output.md>
   ```

   - **Exit 0, PASS:** write `EVAL_PASS.md` (#12). Then (step `finish`, tasks
     `retrospective attack_library playbook harvest_back`) invoke the
     Evaluator with `mode: retrospective` to write `RETROSPECTIVE.md`, and
     run attack-library harvesting (#13), playbook harvesting (#16), and
     harvest-back (#17). The pipeline is complete.
   - **Exit 1, FAIL, N < 5:** run `state.py round N+1`. Invoke the Generator
     once (step `revision`, task `generator`), passing the explicit
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
| `conflicts/round_N.md` | Generator (entries), Evaluator (status) | Evaluator, all reviewers, Orchestrator |
| `pipeline-state/state.json` | Orchestrator, only via `state.py` | Orchestrator (resume) |
| `pipeline-state/round.md` | `state.py round` | All reviewer agents |
| `pipeline-state/progress.md` | Generator (phase transitions + one `REVISION COMPLETE` record per revision pass) | Orchestrator, Architect, Design Critic |
| `pipeline-state/checkpoint.md` | Evaluator (round state) | Audit log only |
| `pipeline-state/architecture-checkpoint.md` | Architect (round state) | Audit log only |
| `pipeline-state/ux-checkpoint.md` | Design Critic (round state) | Audit log only |
| `pipeline-state/security-checkpoint.md` | Security Prober (round state) | Audit log only |
| `pipeline-state/session.md` | Generator (per-feature progress) | Orchestrator (resume) |
| `pipeline-state/user-intervention.md` | Orchestrator (raw log of "Pause build" messages and escalation answers) | User only |
| `pipeline-state/cost.md` | Orchestrator (start and end time of every agent invocation) | Orchestrator (build limits) |
| `pipeline-state/ship-gate.md` | Template (mirror of `gate.py`) | Orchestrator, user |
| `pipeline-state/attack-library.md` | Orchestrator only (appends reviewers' Proposed Probes after the build, #13) | Architect, Design Critic, Security Prober (own shard only) |
| `pipeline-state/playbook.md` | Orchestrator (post-build lesson harvesting) | Generator only (never reviewers) |
| `pipeline-state/build-ledger.md` | Orchestrator (one row per build, via harvest PR) | Orchestrator, user (gate calibration) |
| `.claude/scripts/gate.py` | Template (canonical gate) | Orchestrator (runs each round) |
| `.claude/scripts/state.py` | Template | Orchestrator (every state change) |
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
