#!/usr/bin/env python3
"""Ship gate for the ACES pipeline.

Reads the four reviewer reports for one round straight from disk, extracts
each fenced ```score-block```, validates it strictly, and decides PASS/FAIL
on the state of the build that actually ships. No orchestrator transcription,
no hand arithmetic.

Usage:
    python3 .claude/scripts/gate.py <round> [--tier restrained|standard|bold]

Exit codes: 0 = PASS, 1 = FAIL, 2 = invalid input (missing report, bad block,
commit mismatch). The last stdout line is always a JSON summary.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ARCH_MOD_BUDGET = 3
DC_MOD_BUDGET = 3
DESIGN_FLOOR = 7
CRAFT_FLOOR = 7
ORIGINALITY_FLOOR = {"restrained": 5, "standard": 7, "bold": 8}

SCHEMAS = {
    "architect": {"reviewer", "commit", "crit", "mod", "min"},
    "design_critic": {"reviewer", "commit", "crit", "mod", "min"},
    "security_prober": {"reviewer", "commit", "security_fail", "not_tested"},
    "evaluator": {"reviewer", "commit", "tier1", "not_tested", "originality", "design", "craft"},
}
REPORTS = {
    "architect": "architecture_review_round_{n}.md",
    "design_critic": "design_critique_round_{n}.md",
    "security_prober": "security_probe_round_{n}.md",
    "evaluator": "eval_report_round_{n}.md",
}
BLOCK_RE = re.compile(r"```score-block\s*\n(.*?)```", re.S)


class Invalid(Exception):
    pass


def parse_block(path, expected):
    if not path.is_file():
        raise Invalid(f"missing report: {path}")
    blocks = BLOCK_RE.findall(path.read_text(encoding="utf-8"))
    if len(blocks) != 1:
        raise Invalid(f"{path}: expected exactly 1 score-block, found {len(blocks)}")
    data = {}
    for line in blocks[0].splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            raise Invalid(f"{path}: malformed line {line!r}")
        k, v = (s.strip() for s in line.split(":", 1))
        if k in data:
            raise Invalid(f"{path}: duplicate key {k}")
        data[k] = v
    keys = set(data)
    if keys != SCHEMAS[expected]:
        raise Invalid(f"{path}: key mismatch; missing={sorted(SCHEMAS[expected]-keys)} "
                      f"unknown={sorted(keys-SCHEMAS[expected])}")
    if data["reviewer"] != expected:
        raise Invalid(f"{path}: reviewer={data['reviewer']!r}, expected {expected!r}")
    out = {"reviewer": expected, "commit": data["commit"]}
    for k in keys - {"reviewer", "commit"}:
        try:
            val = int(data[k])
        except ValueError:
            raise Invalid(f"{path}: {k}={data[k]!r} is not an integer")
        hi = 10 if k in {"originality", "design", "craft"} else 10_000
        if not 0 <= val <= hi:
            raise Invalid(f"{path}: {k}={val} out of range 0..{hi}")
        out[k] = val
    return out


def head_commit():
    try:
        return subprocess.run(["git", "-C", "output", "rev-parse", "--short=12", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main(argv):
    if not argv or not argv[0].isdigit() or int(argv[0]) < 1:
        print("usage: gate.py <round> [--tier restrained|standard|bold]", file=sys.stderr)
        return 2
    n = int(argv[0])
    tier = argv[argv.index("--tier") + 1] if "--tier" in argv else "standard"
    if tier not in ORIGINALITY_FLOOR:
        print(f"gate.py: unknown tier {tier!r}", file=sys.stderr)
        return 2
    try:
        blocks = {r: parse_block(Path(REPORTS[r].format(n=n)), r) for r in REPORTS}
        commits = {b["commit"] for b in blocks.values()}
        if len(commits) != 1:
            raise Invalid(f"reports reviewed different commits: "
                          f"{ {r: b['commit'] for r, b in blocks.items()} }")
        head = head_commit()
        reviewed = commits.pop()
        if head is not None and not head.startswith(reviewed[:7]) and not reviewed.startswith(head[:7]):
            raise Invalid(f"reports reviewed {reviewed}, but output/ HEAD is {head}")
    except Invalid as exc:
        print(f"gate.py: INVALID: {exc}")
        print("JSON:" + json.dumps({"round": n, "result": "INVALID", "reason": str(exc)}))
        return 2

    a, d, e, sp = (blocks["architect"], blocks["design_critic"],
                   blocks["evaluator"], blocks["security_prober"])
    tier2 = (e["originality"] * 2 + e["design"] + e["craft"]) / 4
    checks = {
        "tier1_clear": e["tier1"] == 0 and e["not_tested"] == 0,
        "security_clear": sp["security_fail"] == 0 and sp["not_tested"] == 0,
        "architect_no_critical": a["crit"] == 0,
        "architect_moderate_budget": a["mod"] <= ARCH_MOD_BUDGET,
        "design_critic_no_critical": d["crit"] == 0,
        "design_critic_moderate_budget": d["mod"] <= DC_MOD_BUDGET,
        "originality_floor": e["originality"] >= ORIGINALITY_FLOOR[tier],
        "design_floor": e["design"] >= DESIGN_FLOOR,
        "craft_floor": e["craft"] >= CRAFT_FLOOR,
    }
    passed = all(checks.values())
    # Telemetry only (decision D4): never consulted by the gate.
    open_defect_load = 3 * (a["crit"] + d["crit"]) + (a["mod"] + d["mod"]) + 0.25 * (a["min"] + d["min"])
    for name, ok in checks.items():
        print(f"  [{'x' if ok else ' '}] {name}")
    print(f"Round {n}: {'PASS' if passed else 'FAIL'} (commit {reviewed}, tier {tier}, "
          f"Tier2Quality {tier2:g}, open-defect load {open_defect_load:g})")
    print("JSON:" + json.dumps({
        "round": n, "result": "PASS" if passed else "FAIL", "commit": reviewed,
        "checks": checks, "tier2_quality": tier2, "open_defect_load": open_defect_load,
    }))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
