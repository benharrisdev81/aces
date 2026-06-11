format-version: value-function-v2

# Pipeline Value Function

The pipeline is a minimax game over a single scalar, the **Acceptance Score**.
The Generator maximizes it; the three discriminator agents (Architect, Design
Critic, Evaluator) collectively minimize it by landing confirmed defects.

This file is the canonical definition of the formula. Reading agents consume
it and contribute COUNTS — they do not compute the scalar by hand. The
arithmetic is performed deterministically by `.claude/scripts/score.py`,
which the orchestrator runs each round (see "Computing the Score" below).
Agents are good at arithmetic but not deterministic at it; the script is.

---

## Acceptance Score (per round)

```
Acceptance Score
  = Tier2Quality
    − ArchitectPenalty
    − DesignCriticPenalty
    − EvaluatorPenalty
    − NoveltyDefectPenalty
    − FalsePositivePenalty
```

Weights live in one place — the constants at the top of
`.claude/scripts/score.py`. The definitions below are the human-readable
mirror; if you change a weight, change it in both, in lockstep.

### Tier2Quality  (0 – 10, from Evaluator)

`(Originality × 2 + Design + Craft) ÷ 4`

Originality is double-weighted. Tier2Quality is the only positive
contributor to the scalar — every other term is a penalty.

### ArchitectPenalty  (≥ 0, from Architect)

`(CRITICAL × 3) + (MODERATE × 1) + (MINOR × 0.25)`

The Architect emits the counts; the script multiplies.

### DesignCriticPenalty  (≥ 0, from Design Critic)

`(CRITICAL × 3) + (MODERATE × 1) + (MINOR × 0.25)`

### EvaluatorPenalty  (≥ 0, from Evaluator)

`(Tier1 failures × 4) + (security probe failures × 4) + (NOT TESTED entries × 2)`

A single Tier 1 failure dominates the round, as it should.

### NoveltyDefectPenalty  (≥ 0, from any discriminator)

`(novel defect landed this round × 2)`

A "novel defect" is a probe added to `pipeline-state/attack-library.md`
this round that landed a confirmed flaw. This term rewards genuine
discriminator co-evolution: the score gets harder over time because the
test set grows — but only when a *real* new failure class is found (the
quota is discovery-gated, not mandatory; see the reviewer prompts).

### FalsePositivePenalty  (≥ 0, honest-auditor term)

`(reviewer findings withdrawn or non-reproducing × 1.5)`

This is the counterweight to the adversarial framing. The reviewers' win
condition is landing confirmed defects, so without a cost for *wrong*
findings a faithful optimizer would drift toward manufacturing borderline
findings to "win." A finding counts as a false positive when it is later
withdrawn through `CONFLICT.md` adjudication, or when the Generator
demonstrates it does not reproduce and the next Evaluator round agrees.
The penalty is attributed to the reviewer that raised it (recorded in the
`fp_*` columns of `score-history.md`) so reviewer precision is visible
over time, not just reviewer aggressiveness.

---

## Round-by-Round PASS Threshold (ratchet)

| Round | PASS threshold on Acceptance Score |
|---|---|
| 1     | ≥ 6.5 |
| 2     | ≥ 7.0 |
| 3+    | ≥ 7.5 |

The bar tightens each round to mirror the MODERATE-budget ratchet in
`architect.md`, so a build that merely treads water across rounds will
eventually FAIL on score even with no verdict-failing findings.

**Fable 5 calibration.** This ratchet was raised from the Opus 4.8 values
(5.5 → 6.5 → 7.5) to match Claude Fable 5's higher first-shot correctness —
otherwise round-1 passes would leave the ratchet unengaged. Watch the first
2–3 Fable 5 builds in `score-history.md`: if rounds FAIL on score with zero
verdict-failing findings, the bar is too high — lower it by changing
`THRESHOLDS` in `.claude/scripts/score.py` and this table **in lockstep**.
Do not change either alone.

---

## Gate Precedence (authoritative when gates disagree)

The build is judged by gates in this strict order. A later gate is only
consulted if every earlier gate passes.

1. **Tier 1 gates (absolute).** Any Tier 1 failure — crash, missing/stub
   `must` feature, undocumented deviation, NOT TESTED coverage, failed
   security probe — fails the round outright, regardless of any score.
   No score can rescue a Tier 1 failure.

2. **Acceptance Score ratchet (authoritative tiebreaker).** If all Tier 1
   gates pass, the round PASSES only if the Acceptance Score meets the
   round's threshold above. A round that clears Tier 1 but lands below the
   threshold is **FAIL on score** — the Generator must close the gap.

3. **Tier 2 average (subsumed — not a separate gate).** The old standalone
   "Tier 2 average ≥ 7 / originality-tier threshold" rule is now a
   *component* of the Acceptance Score via `Tier2Quality`, not a parallel
   gate. The Evaluator still computes Originality/Design/Craft and still
   applies the originality-tier floor as an input sanity check, but the
   pass/fail decision flows through the Acceptance Score, not a second
   independent average. This removes the previous ambiguity where a build
   could pass one gate and fail the other with no stated precedence.

CONDITIONAL PASS retains its existing meaning (one targeted fix pass, capped
at one per build) and is decided after gates 1–2, exactly as before.

---

## Computing the Score

The orchestrator does NOT compute the scalar in its head. Each round:

1. Read the machine-readable `SCORE-BLOCK` from each reviewer report (see
   below) and the carried penalties from the previous `score-history.md`
   row (for any reviewer skipped this round under the skip-unaffected
   policy).
2. Assemble one JSON payload (schema documented at the top of
   `.claude/scripts/score.py`).
3. Run: `python3 .claude/scripts/score.py < payload.json`
4. Paste the emitted `score-history.md` row under the table in that file,
   and use the emitted Acceptance Score for the `scoreboard.md` row and
   the `index.md` headline.

This keeps the headline number and the PASS-on-score gate deterministic
rather than model-estimated.

---

## Per-Round Reporting — machine-readable SCORE-BLOCK

Every reviewer ends its report with a fenced block using fixed keys, so the
orchestrator extracts counts without parsing prose. Emit COUNTS, not
products — the script does the multiplication.

Architect / Design Critic:

```score-block
reviewer: architect            # or: design_critic
crit: 0
mod: 0
min: 0
novel_landed: 0                # novel probes added this round that landed
fp_withdrawn: 0                # this reviewer's prior findings withdrawn this round
skipped: false
```

Evaluator (also composes the round total via the script):

```score-block
reviewer: evaluator
tier1: 0
security_fail: 0
not_tested: 0
originality: 0                 # 0-10
design: 0                      # 0-10
craft: 0                       # 0-10
novel_landed: 0
fp_withdrawn: 0
```

---

## Tie-Breaks and Edge Cases

- **No Architect/Design-Critic this round** (skip-unaffected-reviewers
  policy): pass `skipped: true` for that reviewer; the script substitutes
  the carried penalty from the prior `score-history.md` row so the scalar
  stays comparable across rounds. Carry-forward reads from disk, never from
  the orchestrator's memory of an earlier round.
- **CONDITIONAL PASS**: scored as the round's Acceptance Score even though
  a targeted fix follows. The targeted-fix re-evaluation overwrites only the
  affected penalty term, not the full score.
- **Generator declines to fix a finding** (disputes it via `CONFLICT.md`):
  the penalty stands until adjudication. If adjudication withdraws the
  finding, it is recorded as a false positive (`fp_withdrawn`) against the
  reviewer that raised it in the round where the withdrawal is confirmed.

---

## Why this matters

Without one shared scalar, the reviewers and Generator are not playing the
same game — they are running parallel checklists with verbal verdicts. The
scalar makes the minimax explicit. Computing it in code makes it
trustworthy. The false-positive term keeps the adversarial incentive from
degrading reviewer precision. Together they let you plot convergence and
trust the number you are plotting.
