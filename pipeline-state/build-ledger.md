format-version: build-ledger-v1

# Build Ledger

One row per completed build (PASS, UNRECOVERABLE, or a user override the user
chose to harvest), appended through the harvest-back protocol (CLAUDE.md
Responsibility #17). Builds run in per-build clones, so this table — in the
template repo — is the only place cross-build results accumulate.

This is the calibration substrate for the ship gate's constants (the
MODERATE budgets and subscore floors in `.claude/scripts/gate.py`; see
`pipeline-state/ship-gate.md`). A run of builds that fail on one constant
alone means it may be too strict; a run of Round 1 PASSes means the gate may
be too loose. Rows before 2026-10 were judged by the retired score formula;
their Notes keep the old score and threshold.

Columns:
- **Date** — build completion date (UTC)
- **Concept** — short product slug
- **Rounds** — evaluation rounds consumed
- **Verdict**: PASS / UNRECOVERABLE / OVERRIDE (accepted by the user after a gate FAIL)
- **Final open-defect load**: the gate's `open_defect_load` for the final round
- **Probes+** — attack-library probes added by this build's harvest
- **Lessons+** — playbook lessons added by this build's harvest
- **Notes** — one short clause (dominant failure mode, or what made it pass)

| Date | Concept | Rounds | Verdict | Final open-defect load | Probes+ | Lessons+ | Notes |
|---|---|---|---|---|---|---|---|
| 2026-05-14 | cyberpunk-spades | 2 | PASS | — | 0 | 0 | Pre-score era (Tier-2 avg 8.0); R1 fail on debrief/scoring flow, fixed R2 |
| 2026-05-16 | last-war-companion | 1 | PASS | — | 0 | 0 | Pre-score era (Tier-2 avg 7.75); streaming Anthropic API integration; UX fixes in-round |
| 2026-05-18 | texas-holdem | 3 | PASS | — | 0 | 0 | Pre-score era (Tier-2 avg 8.3); MTT multi-table wiring took two extra rounds |
| 2026-05-20 | math-runner | 1 | PASS | — | 0 | 2 | Pre-score era (Tier-2 avg 8.0); DC landed 4 CRIT in-round; Architect MODs (unseeded RNG) accepted at PASS |
| 2026-06-02 | cipher-diary (gan-trial-one) | 2 | PASS | — | 2 | 2 | Old score 7.0 (threshold 6.5). Hidden-overlay CRIT + pre-auth stack leak; clean 2-round convergence under the old 5.5/6.5 score thresholds |
| 2026-06-09 | card-game (Parlour suite) | 2 | PASS | — | 2 | 1 | Old score 7.5 (threshold 6.5). Gate precedence proved out: EVAL_PASS held below the score threshold by open Architect MODs until R2 cleanup |
| 2026-06-12 | streakline (habit tracker) | 2 | PASS | — | 0 | 3 | Old score 7.25 (threshold 7.0). First build on the 6.5/7.0/7.5 score thresholds + harvested memory (playbook lessons pre-empted 3 prior failure classes; harvested probes all held). R1 mathematically unwinnable on score (reviewer penalties 5.5 vs 6.5 with both reviewers PASS) — calibration signal. R2 pass hinged on Originality 7→8 (at 7: 6.75 FAIL); double-weighted Originality swings 0.5/point. |
