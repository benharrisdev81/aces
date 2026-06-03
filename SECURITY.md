# Security Policy

## Reporting a Vulnerability

Please **do not** open a public issue for security problems.

Report vulnerabilities privately through GitHub's
[private vulnerability reporting](https://github.com/benharrisdev81/aces/security/advisories/new)
("Report a vulnerability" under the **Security** tab). This routes the report
directly and privately to the maintainers.

When reporting, please include:

- A description of the issue and its impact.
- Steps to reproduce (or a proof of concept).
- The affected file(s) or pipeline stage, if known.

You can expect an initial acknowledgement within **5 business days**. Once a
fix is available, we will coordinate disclosure with you.

## Scope

ACES is a template that orchestrates AI sub-agents to generate code. Relevant
security considerations include:

- **Generated-code safety** — issues in the Generator's security baseline
  (e.g. patterns that would emit secrets in source, injectable queries, or
  unsafe `eval`).
- **Pipeline configuration** — overly permissive defaults shipped in
  `.claude/settings.json` or agent prompts.
- **The scoring script** — `.claude/scripts/score.py`.

Note that ACES executes AI-generated code and shell commands as part of its
normal operation. Run it in an environment you trust, and review the
permissions in `.claude/settings.json` before use.
