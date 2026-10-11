#!/usr/bin/env python3
"""Pipeline state for the ACES orchestrator.

pipeline-state/state.json is the single record of where a build is. The
orchestrator changes it only through this script, so no model ever edits
the JSON by hand. Resume reads it and re-runs every task in `pending`.

Usage (run from the build clone's root):
    state.py init                    start a fresh state file
    state.py get [KEY]               print the whole state, or one key, as JSON
    state.py set KEY VALUE           set a key; VALUE is parsed as JSON if it can be
    state.py round N                 start round N (also rewrites round.md)
    state.py step NAME [TASK ...]    enter a step; its tasks become `pending`
    state.py done TASK               move TASK from `pending` to `done`

Exit codes: 0 = ok, 2 = usage error or missing key.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE = Path("pipeline-state/state.json")
ROUND_MD = Path("pipeline-state/round.md")

FRESH = {
    "round": 0,
    "step": "clarify",
    "pending": [],
    "done": [],
    "commit": None,
    "escalation": None,
    "generator_invocations": 0,
    "build_started": None,
    "dormant": [],
}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load():
    if not STATE.is_file():
        raise SystemExit("state.py: no pipeline-state/state.json; run: state.py init")
    return json.loads(STATE.read_text(encoding="utf-8"))


def save(state):
    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE)


def parse_value(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def main(argv):
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd == "init" and not args:
        state = dict(FRESH, build_started=now())
        save(state)
    elif cmd == "get" and len(args) <= 1:
        state = load()
        if args and args[0] not in state:
            print(f"state.py: no key {args[0]!r}", file=sys.stderr)
            return 2
        print(json.dumps(state[args[0]] if args else state, indent=2))
    elif cmd == "set" and len(args) == 2:
        state = load()
        state[args[0]] = parse_value(args[1])
        save(state)
    elif cmd == "round" and len(args) == 1 and args[0].isdigit():
        state = load()
        state["round"] = int(args[0])
        save(state)
        ROUND_MD.write_text(f"Current Round: {args[0]}\nStarted: {now()}\n", encoding="utf-8")
    elif cmd == "step" and args:
        state = load()
        state["step"], state["pending"], state["done"] = args[0], list(args[1:]), []
        save(state)
    elif cmd == "done" and len(args) == 1:
        state = load()
        if args[0] not in state["pending"]:
            print(f"state.py: {args[0]!r} is not pending", file=sys.stderr)
            return 2
        state["pending"].remove(args[0])
        state["done"].append(args[0])
        save(state)
    else:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
