format-version: build-ledger-v1

# Build Ledger

One row per completed build (PASS or UNRECOVERABLE), appended through the
harvest-back protocol (CLAUDE.md Responsibility #17). Builds run in per-build
clones, so this table — in the template repo — is the only place cross-build
results accumulate.

This is the calibration substrate: the threshold re-baselining watch-item in
`pipeline-state/value-function.md` ("Fable 5 calibration") reads this table.
A run of builds whose Verdict is FAIL-on-score with zero verdict-failing
findings means the ratchet is too high; a run of round-1 PASSes means it is
too low.

Columns:
- **Date** — build completion date (UTC)
- **Concept** — short product slug
- **Rounds** — evaluation rounds consumed
- **Verdict** — PASS / CONDITIONAL→PASS / UNRECOVERABLE
- **Final Score** — Acceptance Score of the final round
- **Thr** — threshold in force at the final round
- **Probes+** — attack-library probes added by this build's harvest
- **Lessons+** — playbook lessons added by this build's harvest
- **Notes** — one short clause (dominant failure mode, or what made it pass)

| Date | Concept | Rounds | Verdict | Final Score | Thr | Probes+ | Lessons+ | Notes |
|---|---|---|---|---|---|---|---|---|
| _(no builds harvested yet)_ | | | | | | | | |
