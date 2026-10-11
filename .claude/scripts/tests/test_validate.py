#!/usr/bin/env python3
"""Self-contained tests for validate.py. Run: python3 .claude/scripts/tests/test_validate.py"""
import subprocess
import sys
import tempfile
from pathlib import Path

VALIDATE = Path(__file__).resolve().parent.parent / "validate.py"

SPEC = "format-version: planner-v1\n" + "".join(
    f"<{t}>\nx{' standard' if t == 'originality_tier' else ''}\n</{t}>\n"
    for t in ["planner_assumptions", "product_overview", "domain_glossary",
              "conceptual_data_model", "scale_targets", "originality_tier",
              "visual_design_language", "core_feature_deliverables", "explicit_non_goals"])
REPORT = ("format-version: architecture-review-v1\n# Architecture Review\n\n```score-block\n"
          "reviewer: architect\ncommit: a1b2c3d4e5f6\ncrit: 0\nmod: 1\nmin: 2\n```\n")

CASES = [
    # (name, file name, content, expected exit)
    ("correct spec header", "planner_output.md", SPEC, 0),
    ("fenced spec header", "planner_output.md", "```\n" + SPEC.replace("planner-v1\n", "planner-v1\n```\n", 1), 1),
    ("spec missing a section", "planner_output.md", SPEC.replace("<scale_targets>", "<scale>"), 1),
    ("spec with an unknown tier", "planner_output.md", SPEC.replace(" standard", " wild"), 1),
    ("correct report", "architecture_review_round_2.md", REPORT, 0),
    ("report with a bad score-block", "architecture_review_round_2.md", REPORT.replace("mod: 1", "mdo: 1"), 1),
    ("report with two score-blocks", "architecture_review_round_2.md", REPORT + REPORT.split("\n", 1)[1], 1),
    ("handoff missing How to Stop", "HANDOFF.md",
     "format-version: handoff-v1\n## Build Summary\n## How to Run\n## Feature Checklist\n"
     "## Known Issues\n## Assumptions Made\n", 1),
    ("unknown file name", "notes.md", "hello\n", 2),
]


def main():
    failures = 0
    for name, fname, content, expected in CASES:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / fname
            path.write_text(content, encoding="utf-8")
            got = subprocess.run([sys.executable, "-I", str(VALIDATE), str(path)],
                                 capture_output=True, text=True).returncode
        ok = got == expected
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'} exit={got} expected={expected}  {name}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
