#!/usr/bin/env python3
"""Self-contained tests for gate.py.

Run: python3 .claude/scripts/tests/test_gate.py [path/to/gate.py]
With no argument it tests ../gate.py, relative to this file.

Builds a throwaway project dir with a real output/ git repo and four reviewer
reports, mutates them per case, and asserts gate.py's exit code (0 PASS,
1 FAIL, 2 INVALID). Needs only python3 and git.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

GATE = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent / "gate.py").resolve()

BASE = {
    "architecture_review_round_3.md": ("architect", {"crit": 0, "mod": 1, "min": 4}),
    "design_critique_round_3.md": ("design_critic", {"crit": 0, "mod": 1, "min": 4}),
    "security_probe_round_3.md": ("security_prober", {"security_fail": 0, "not_tested": 0}),
    "eval_report_round_3.md": ("evaluator", {"tier1": 0, "not_tested": 0,
                                             "originality": 7, "design": 7, "craft": 7}),
}


def write_reports(root, head, overrides=None, drop=None, extra_line=None, commit_for=None):
    overrides = overrides or {}
    for fname, (reviewer, fields) in BASE.items():
        if fname == drop:
            continue
        f = dict(fields)
        f.update(overrides.get(fname, {}))
        commit = (commit_for or {}).get(fname, head)
        lines = [f"reviewer: {reviewer}", f"commit: {commit}"] + [f"{k}: {v}" for k, v in f.items()]
        if extra_line and extra_line[0] == fname:
            lines.append(extra_line[1])
        body = "# report\n\n```score-block\n" + "\n".join(lines) + "\n```\n"
        (root / fname).write_text(body, encoding="utf-8")


def run(root, *args):
    return subprocess.run([sys.executable, "-I", str(GATE), "3", *args],
                          cwd=root, capture_output=True, text=True).returncode


CASES = [
    # (name, kwargs for write_reports, extra gate args, expected exit)
    ("clean build, 7/7/7, round 3", {}, [], 0),
    ("restrained tier, originality 5", {"overrides": {"eval_report_round_3.md": {"originality": 5}}},
     ["--tier", "restrained"], 0),
    ("standard tier, originality 5", {"overrides": {"eval_report_round_3.md": {"originality": 5}}}, [], 1),
    ("open architect CRITICAL", {"overrides": {"architecture_review_round_3.md": {"crit": 1}}}, [], 1),
    ("design critic over MOD budget", {"overrides": {"design_critique_round_3.md": {"mod": 4}}}, [], 1),
    ("security probe failed", {"overrides": {"security_probe_round_3.md": {"security_fail": 1}}}, [], 1),
    ("security probe not tested", {"overrides": {"security_probe_round_3.md": {"not_tested": 1}}}, [], 1),
    ("evaluator tier1 failure", {"overrides": {"eval_report_round_3.md": {"tier1": 1}}}, [], 1),
    ("craft below floor", {"overrides": {"eval_report_round_3.md": {"craft": 6}}}, [], 1),
    ("unknown key", {"extra_line": ("design_critique_round_3.md", "verdict: PASS")}, [], 2),
    ("out of range subscore", {"overrides": {"eval_report_round_3.md": {"craft": 15}}}, [], 2),
    ("negative count", {"overrides": {"architecture_review_round_3.md": {"min": -1}}}, [], 2),
    ("missing security report", {"drop": "security_probe_round_3.md"}, [], 2),
    ("one reviewer on stale commit", {"commit_for": {"architecture_review_round_3.md": "deadbeef0000"}}, [], 2),
    ("all reviewers on stale commit", {"commit_for": {f: "deadbeef0000" for f in BASE}}, [], 2),
    ("unknown tier", {}, ["--tier", "wild"], 2),
]


def main():
    failures = 0
    for name, kwargs, args, expected in CASES:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            git = ["git", "-C", str(root / "output")]
            subprocess.run(git + ["init", "-q"], check=True)
            subprocess.run(git + ["-c", "user.email=t@t", "-c", "user.name=t",
                                  "commit", "-q", "--allow-empty", "-m", "x"], check=True)
            head = subprocess.run(git + ["rev-parse", "--short=12", "HEAD"],
                                  capture_output=True, text=True, check=True).stdout.strip()
            write_reports(root, head, **kwargs)
            got = run(root, *args)
            ok = got == expected
            failures += not ok
            print(f"{'ok  ' if ok else 'FAIL'} exit={got} expected={expected}  {name}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
