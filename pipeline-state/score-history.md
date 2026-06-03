format-version: score-history-v2

# Score History

One row per round, appended by the orchestrator from the output of
`.claude/scripts/score.py`. See `pipeline-state/value-function.md` for the
formula and `score.py` for the deterministic arithmetic.

This table is also the **carry-forward source of truth**: when a reviewer is
skipped in a later round (skip-unaffected-reviewers policy), the orchestrator
reads that reviewer's penalty from this table's prior row and passes it to
the script as a carried value — carry-forward reads from disk, never from the
orchestrator's memory of an earlier round.

Columns:
- `Tier2Q` — Tier2Quality (Originality×2 + Design + Craft) ÷ 4
- `ArchPen` / `UXPen` / `EvalPen` — per-reviewer penalties (carry-forward reads these)
- `NovPen` — NoveltyDefectPenalty
- `FPPen` — FalsePositivePenalty (honest-auditor term)
- `Score` — Acceptance Score
- `Thr` — round threshold
- `Verdict` — PASS-on-score / FAIL-on-score (Tier 1 gates are decided separately)

| Round | Tier2Q | ArchPen | UXPen | EvalPen | NovPen | FPPen | Score | Thr | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| _(no rounds yet)_ | | | | | | | | | |
