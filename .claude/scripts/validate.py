#!/usr/bin/env python3
"""Validate one pipeline handoff file before the next agent reads it.

Checks that line 1 is the expected header (plain text, no code fence), that
the format's required sections are present, and, for the four reviewer
reports, that the file holds exactly one valid score-block (using gate.py's
parser, so the two scripts can never disagree).

Usage:
    python3 .claude/scripts/validate.py <file>

The format is chosen from the file name. Exit codes: 0 = valid, 1 = invalid,
2 = usage error or unknown file name.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402

PLANNER_SECTIONS = ["planner_assumptions", "product_overview", "domain_glossary",
                    "conceptual_data_model", "scale_targets", "originality_tier",
                    "visual_design_language", "core_feature_deliverables",
                    "explicit_non_goals"]
CLARIFIER_SECTIONS = ["original_concept", "success_criteria", "target_user", "non_goals",
                      "constraints_and_integrations", "resolved_ambiguities",
                      "clarified_concept", "planner_priming"]
HANDOFF_HEADINGS = ["## Build Summary", "## How to Run", "## How to Stop",
                    "## Feature Checklist", "## Known Issues", "## Assumptions Made"]

# file-name pattern -> (line-1 header, required XML tags, required headings, reviewer for score-block)
FORMATS = [
    (r"clarifier_output\.md", "<clarification_report>", CLARIFIER_SECTIONS, [], None),
    (r"planner_output\.md", "format-version: planner-v1", PLANNER_SECTIONS, [], None),
    (r"HANDOFF\.md", "format-version: handoff-v1", [], HANDOFF_HEADINGS, None),
    (r"BUILD_NOTES\.md", "format-version: build-notes-v1", [], [], None),
    (r"VERIFY_NOTES\.md", "format-version: verify-notes-v1", [], [], None),
    (r"architecture_review_round_\d+\.md", "format-version: architecture-review-v1", [], [], "architect"),
    (r"design_critique_round_\d+\.md", "format-version: design-critique-v1", [], [], "design_critic"),
    (r"security_probe_round_\d+\.md", "format-version: security-probe-v1", [], [], "security_prober"),
    (r"eval_report_round_\d+\.md", "format-version: eval-report-v1", [], [], "evaluator"),
    (r"EVAL_PASS\.md", "format-version: eval-pass-v1", [], [], None),
    (r"EVAL_UNRECOVERABLE\.md", "format-version: eval-unrecoverable-v1", [], [], None),
    (r"RETROSPECTIVE\.md", "format-version: retrospective-v1", [], [], None),
    (r"ESCALATION_REQUESTED\.md", "format-version: escalation-v1", [], [], None),
]


def validate(path):
    """Return a list of problems; an empty list means the file is valid."""
    for pattern, header, tags, headings, reviewer in FORMATS:
        if re.fullmatch(pattern, path.name):
            break
    else:
        raise KeyError(path.name)
    if not path.is_file():
        return [f"{path}: file does not exist"]
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    problems = []
    first = lines[0].strip() if lines else ""
    if first != header:
        hint = " (remove the code fence)" if first.startswith("```") else ""
        problems.append(f"line 1 is {first!r}, expected {header!r}{hint}")
    for tag in tags:
        if f"<{tag}>" not in text or f"</{tag}>" not in text:
            problems.append(f"missing <{tag}> section")
    if path.name == "clarifier_output.md" and "</clarification_report>" not in text:
        problems.append("missing closing </clarification_report>")
    if path.name == "planner_output.md":
        m = re.search(r"<originality_tier>(.*?)</originality_tier>", text, re.S)
        if m and not re.search(r"\b(restrained|standard|bold)\b", m.group(1)):
            problems.append("<originality_tier> names none of restrained, standard, bold")
    for heading in headings:
        if not re.search(rf"^\s*{re.escape(heading)}\s*$", text, re.M):
            problems.append(f"missing heading {heading!r}")
    if reviewer:
        try:
            gate.parse_block(path, reviewer)
        except gate.Invalid as exc:
            problems.append(f"score-block: {exc}")
    return problems


def main(argv):
    if len(argv) != 1:
        print("usage: validate.py <file>", file=sys.stderr)
        return 2
    path = Path(argv[0])
    try:
        problems = validate(path)
    except KeyError:
        print(f"validate.py: no known format for {path.name}", file=sys.stderr)
        return 2
    for p in problems:
        print(f"validate.py: {path}: {p}")
    if not problems:
        print(f"validate.py: {path}: valid")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
