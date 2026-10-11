format-version: ship-gate-v1

# Ship Gate

The ship gate decides every round. It is `.claude/scripts/gate.py`; this page
is its human-readable mirror. If you change a rule or a constant, change the
script and this page together, and keep `.claude/scripts/tests/test_gate.py`
passing.

## How it runs

When all four reviewer reports for round N exist, the orchestrator runs:

```
python3 .claude/scripts/gate.py N --tier <restrained | standard | bold>
```

The tier comes from the spec's `<originality_tier>` and defaults to
`standard`. The script reads the four reports straight from disk, so nobody
transcribes a number.

| Exit | Result | What the orchestrator does next |
|---|---|---|
| 0 | PASS | Writes `EVAL_PASS.md`, then runs the retrospective and harvesting |
| 1 | FAIL | Starts the next round, or writes `EVAL_UNRECOVERABLE.md` after Round 5 |
| 2 | INVALID | Re-invokes the offending reviewer once, then escalates |

## Score-blocks

Each report holds exactly one fenced `score-block` with exactly these keys.
`commit` is `git -C output rev-parse --short=12 HEAD`, read before the
reviewer starts. Counts are non-negative integers. Subscores are integers
from 0 to 10.

| Report | `reviewer:` | Other keys |
|---|---|---|
| `architecture_review_round_N.md` | `architect` | `commit`, `crit`, `mod`, `min` |
| `design_critique_round_N.md` | `design_critic` | `commit`, `crit`, `mod`, `min` |
| `security_probe_round_N.md` | `security_prober` | `commit`, `security_fail`, `not_tested` |
| `eval_report_round_N.md` | `evaluator` | `commit`, `tier1`, `not_tested`, `originality`, `design`, `craft` |

A missing report, a missing, unknown, or duplicate key, an out-of-range
value, or a second block makes the round INVALID.

## Pass conditions

The round is INVALID unless all four reports name the same commit and that
commit is `output/` HEAD. Otherwise it passes only if every condition holds:

1. Evaluator: `tier1` is 0 and `not_tested` is 0.
2. Security Prober: `security_fail` is 0 and `not_tested` is 0.
3. Architect: `crit` is 0 and `mod` is at most 3 (`ARCH_MOD_BUDGET`).
4. Design Critic: `crit` is 0 and `mod` is at most 3 (`DC_MOD_BUDGET`).
5. Originality is at or above the tier floor: restrained 5, standard 7,
   bold 8.
6. Design is at least 7 and Craft is at least 7.

MINOR findings never count. Nothing is averaged, nothing carries over from
an earlier round, and the budgets and floors are the same in every round.

## Statistics (never gate)

The gate also prints two numbers that never affect the result:

- `tier2_quality`: (Originality × 2 + Design + Craft) ÷ 4.
- `open_defect_load`: 3 × CRITICAL + MODERATE + 0.25 × MINOR, summed over
  the Architect and the Design Critic.

The final round's `open_defect_load` goes into `build-ledger.md`.

## Changing the gate

Change a budget or a floor only when `build-ledger.md` shows a pattern, such
as a run of builds that fail on one constant alone, or a run of Round 1
PASSes. Change `gate.py`, this page, and the tests in the same commit.
