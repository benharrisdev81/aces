format-version: scoreboard-v1

# Generator vs. Discriminator Scoreboard

One row per round. Appended by the orchestrator after each Evaluator
verdict. The pipeline is a minimax game (see
`pipeline-state/value-function.md`); this file makes the
Generator-vs-Discriminator outcome of each round visible at a glance.

A round is a **Generator WIN** if every reviewer agent issued PASS on
first contact (no revision passes consumed) AND the Acceptance Score
cleared the round's threshold.

A round is a **Discriminator WIN** if any reviewer landed a confirmed
finding (CRITICAL/MODERATE for Architect or Design Critic; Tier 1 for
Evaluator) that forced a revision pass.

CONDITIONAL PASS rounds are recorded as **Draw** — neither side
unambiguously won.

| Round | Outcome | Score | Flaw landed | Notes |
|---|---|---|---|---|
| _(no rounds yet)_ | | | | |
