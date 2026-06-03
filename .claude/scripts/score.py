#!/usr/bin/env python3
"""Deterministic Acceptance Score calculator for the adversarial pipeline.

This script is the single source of truth for the arithmetic defined in
`pipeline-state/value-function.md`. The orchestrator runs it instead of
computing the score by hand, so the headline number and the PASS-on-score
gate are deterministic rather than model-estimated.

Separation of concerns:
  - Reviewer agents emit COUNTS (crit/mod/min, tier1, etc.) in a fenced
    machine-readable block at the end of their reports.
  - The orchestrator extracts those counts into one JSON payload and pipes
    it to this script.
  - This script does ALL multiplication, summation, threshold comparison,
    and outcome classification. No agent multiplies by hand.

Usage:
    python3 .claude/scripts/score.py < payload.json
    cat payload.json | python3 .claude/scripts/score.py
    python3 .claude/scripts/score.py payload.json

Input JSON schema (all keys optional unless noted; missing numbers default
to 0, missing booleans to false):

    {
      "round": 1,                      // required, int >= 1

      "tier2": {                       // Evaluator Tier-2 subscores, 0-10
        "originality": 7,
        "design": 7,
        "craft": 7
      },

      "architect":     {"crit": 0, "mod": 0, "min": 0, "skipped": false},
      "design_critic": {"crit": 0, "mod": 0, "min": 0, "skipped": false},
      "evaluator":     {"tier1": 0, "security_fail": 0, "not_tested": 0},

      "novel_defects": 0,              // novel-probe landings, all reviewers
      "false_positives": 0,           // findings later withdrawn (honest auditor)

      // Carry-forward: when a reviewer is skipped this round, pass the
      // penalty it contributed last round so the scalar stays comparable.
      // The orchestrator reads these from the prior score-history.md row.
      "carry": {"architect": 0.0, "design_critic": 0.0}
    }

Output: human-readable breakdown on stdout, plus two ready-to-paste lines
(a score-history.md row and a scoreboard.md row) and a machine-readable
JSON summary on the final line for any downstream tooling.
"""

import json
import sys

# --- weights (mirror pipeline-state/value-function.md; change in lockstep) ---
W_CRIT = 3.0
W_MOD = 1.0
W_MIN = 0.25
W_TIER1 = 4.0
W_SECURITY = 4.0
W_NOT_TESTED = 2.0
W_NOVELTY = 2.0
W_FALSE_POSITIVE = 1.5  # honest-auditor penalty per withdrawn finding

# Round-by-round PASS threshold ratchet.
THRESHOLDS = {1: 5.5, 2: 6.5}
THRESHOLD_3_PLUS = 7.5


def threshold_for(round_num):
    return THRESHOLDS.get(round_num, THRESHOLD_3_PLUS)


def reviewer_penalty(block):
    """CRIT*3 + MOD*1 + MIN*0.25 for an architect/design_critic block."""
    return (
        block.get("crit", 0) * W_CRIT
        + block.get("mod", 0) * W_MOD
        + block.get("min", 0) * W_MIN
    )


def main():
    raw = ""
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        with open(args[0], "r", encoding="utf-8") as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.read()

    if not raw.strip():
        sys.exit("score.py: no JSON payload provided (stdin or file arg)")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"score.py: invalid JSON payload: {exc}")

    round_num = data.get("round")
    if not isinstance(round_num, int) or round_num < 1:
        sys.exit("score.py: 'round' is required and must be an int >= 1")

    tier2 = data.get("tier2", {})
    originality = tier2.get("originality", 0)
    design = tier2.get("design", 0)
    craft = tier2.get("craft", 0)
    tier2_quality = (originality * 2 + design + craft) / 4

    arch = data.get("architect", {})
    uxc = data.get("design_critic", {})
    ev = data.get("evaluator", {})
    carry = data.get("carry", {})

    # Reviewer penalties — use carry-forward value when the reviewer was
    # skipped this round (skip-unaffected-reviewers policy).
    if arch.get("skipped"):
        arch_penalty = float(carry.get("architect", 0.0))
        arch_note = "(carried forward; Architect skipped)"
    else:
        arch_penalty = reviewer_penalty(arch)
        arch_note = f"(CRIT {arch.get('crit',0)}, MOD {arch.get('mod',0)}, MIN {arch.get('min',0)})"

    if uxc.get("skipped"):
        ux_penalty = float(carry.get("design_critic", 0.0))
        ux_note = "(carried forward; Design Critic skipped)"
    else:
        ux_penalty = reviewer_penalty(uxc)
        ux_note = f"(CRIT {uxc.get('crit',0)}, MOD {uxc.get('mod',0)}, MIN {uxc.get('min',0)})"

    eval_penalty = (
        ev.get("tier1", 0) * W_TIER1
        + ev.get("security_fail", 0) * W_SECURITY
        + ev.get("not_tested", 0) * W_NOT_TESTED
    )

    novelty_penalty = data.get("novel_defects", 0) * W_NOVELTY
    false_positive_penalty = data.get("false_positives", 0) * W_FALSE_POSITIVE

    acceptance = (
        tier2_quality
        - arch_penalty
        - ux_penalty
        - eval_penalty
        - novelty_penalty
        - false_positive_penalty
    )

    threshold = threshold_for(round_num)
    met = acceptance >= threshold

    # --- human-readable breakdown -------------------------------------------
    def fmt(x):
        return f"{x:.2f}".rstrip("0").rstrip(".") if x % 1 else f"{int(x)}"

    print(f"Acceptance Score — Round {round_num}")
    print(f"  Tier2Quality:           {fmt(tier2_quality):>7}   "
          f"(Orig {originality}×2, Design {design}, Craft {craft})")
    print(f"  ArchitectPenalty:      -{fmt(arch_penalty):>7}   {arch_note}")
    print(f"  DesignCriticPenalty:   -{fmt(ux_penalty):>7}   {ux_note}")
    print(f"  EvaluatorPenalty:      -{fmt(eval_penalty):>7}   "
          f"(Tier1 {ev.get('tier1',0)}, sec {ev.get('security_fail',0)}, "
          f"NOT-TESTED {ev.get('not_tested',0)})")
    print(f"  NoveltyDefectPenalty:  -{fmt(novelty_penalty):>7}   "
          f"(novel landings {data.get('novel_defects',0)})")
    print(f"  FalsePositivePenalty:  -{fmt(false_positive_penalty):>7}   "
          f"(withdrawn findings {data.get('false_positives',0)})")
    print("  " + "-" * 40)
    print(f"  Acceptance Score:       {fmt(acceptance):>7}   "
          f"(threshold {fmt(threshold)}, met: {'yes' if met else 'no'})")
    print()

    # --- ready-to-append rows ------------------------------------------------
    verdict = "PASS-on-score" if met else "FAIL-on-score"
    history_row = (
        f"| {round_num} | {fmt(tier2_quality)} | {fmt(arch_penalty)} | "
        f"{fmt(ux_penalty)} | {fmt(eval_penalty)} | {fmt(novelty_penalty)} | "
        f"{fmt(false_positive_penalty)} | {fmt(acceptance)} | {fmt(threshold)} | "
        f"{verdict} |"
    )
    print("score-history.md row (append under the table):")
    print(history_row)
    print()

    # --- machine-readable summary (last line) --------------------------------
    summary = {
        "round": round_num,
        "tier2_quality": round(tier2_quality, 4),
        "architect_penalty": round(arch_penalty, 4),
        "design_critic_penalty": round(ux_penalty, 4),
        "evaluator_penalty": round(eval_penalty, 4),
        "novelty_penalty": round(novelty_penalty, 4),
        "false_positive_penalty": round(false_positive_penalty, 4),
        "acceptance_score": round(acceptance, 4),
        "threshold": threshold,
        "score_gate_met": met,
    }
    print("JSON:" + json.dumps(summary))


if __name__ == "__main__":
    main()
