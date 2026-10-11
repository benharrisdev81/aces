#!/usr/bin/env python3
"""Self-contained tests for state.py. Run: python3 .claude/scripts/tests/test_state.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

STATE_PY = (Path(__file__).resolve().parent.parent / "state.py")


def run(root, *args):
    r = subprocess.run([sys.executable, "-I", str(STATE_PY), *args],
                       cwd=root, capture_output=True, text=True)
    return r.returncode, r.stdout


def main():
    checks = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pipeline-state").mkdir()
        checks.append(("get before init fails", run(root, "get")[0] != 0))
        checks.append(("init", run(root, "init")[0] == 0))
        run(root, "set", "commit", "a1b2c3d4e5f6")
        checks.append(("set then get string", json.loads(run(root, "get", "commit")[1]) == "a1b2c3d4e5f6"))
        run(root, "set", "escalation", '{"agent": "evaluator", "question": "A or B?"}')
        checks.append(("set then get object",
                       json.loads(run(root, "get", "escalation")[1]) == {"agent": "evaluator", "question": "A or B?"}))
        run(root, "round", "2")
        checks.append(("round sets state", json.loads(run(root, "get", "round")[1]) == 2))
        checks.append(("round writes round.md",
                       (root / "pipeline-state/round.md").read_text().startswith("Current Round: 2\n")))
        run(root, "step", "review", "architect", "design_critic")
        run(root, "done", "architect")
        state = json.loads(run(root, "get")[1])
        checks.append(("step and done", state["pending"] == ["design_critic"] and state["done"] == ["architect"]))
        checks.append(("done on a non-pending task fails", run(root, "done", "evaluator")[0] == 2))
        checks.append(("unknown key fails", run(root, "get", "nope")[0] == 2))
        run(root, "incr", "generator_invocations")
        checks.append(("incr", run(root, "incr", "generator_invocations")[1].strip() == "2"))
        checks.append(("incr on a non-number fails", run(root, "incr", "step")[0] == 2))
    failures = 0
    for name, ok in checks:
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
    print(f"\n{len(checks) - failures}/{len(checks)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
