# Contributing to ACES

Thanks for your interest in improving ACES. This project is a template for an
autonomous, adversarial multi-agent build pipeline — most of it is prompt
engineering (the sub-agent definitions in `.claude/agents/`), orchestration
rules (`CLAUDE.md`), and the shared scoring logic (`.claude/scripts/score.py`).

## Ways to contribute

- **Improve a sub-agent prompt** — sharpen the Clarifier, Planner, Generator,
  Architect, Design Critic, or Evaluator.
- **Refine the game mechanics** — the value function, scoreboard, or
  attack-library schema under `pipeline-state/`.
- **Fix or extend the scorer** — `.claude/scripts/score.py`.
- **Documentation** — clarify the README or `CLAUDE.md` orchestration steps.

## Workflow

1. Open an issue first for anything non-trivial, so we can agree on the
   approach before you invest time.
2. Fork the repo and create a feature branch (`git checkout -b my-change`).
3. Make your change. Keep edits focused and consistent with the surrounding
   style — match the existing tone and structure of the agent prompts.
4. If you change `score.py`, make sure it still runs and produces a valid row.
5. Open a pull request using the PR template and link the related issue.

## Guidelines

- **Keep the format-version contracts intact.** Many handoff files begin with a
  `format-version:` header that agents validate. If you change a file's
  structure, bump its version and update the table in `CLAUDE.md`.
- **No secrets, ever.** Don't commit API keys, tokens, or `.env` files. The
  Generator's own security baseline forbids this — the repo should model it.
- **Preserve the adversarial framing.** Changes should keep the
  Generator-vs-discriminator minimax structure coherent (see
  `pipeline-state/value-function.md`).

## License

By contributing, you agree that your contributions will be licensed under the
[Apache License 2.0](LICENSE) that covers this project.
