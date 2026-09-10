# Development Guide

## CLI Rules

- Use `chatstyle>=0.2.0,<0.3.0` and `chatenv>=0.2.11,<0.3.0` as the canonical CLI and environment runtime.
- Keep the root command explicitly named `chatbd` and use ChatStyle `add_tree_option()` for `--tree` and `--tree-brief`; do not add a package-local tree renderer.
- `--tree` must include registered parameter signatures, while `--tree-brief` must preserve the same command hierarchy without signatures.
- Prefer `CommandSchema`, `CommandField`, `add_interactive_option()`, and `resolve_command_inputs()` for new commands.
- Missing required args should auto-enter interactive mode when recoverable.
- `-i` forces interactive mode; `-I` disables prompting and must fail fast.
- Prompt defaults must match actual execution defaults.
- Sensitive values must stay masked in prompts and summaries.
- Prefer lazy imports in CLI wiring and keep implementation imports local when possible.

## Docs and Tests

- Use doc-first CLI testing.
- Put real CLI coverage under `tests/cli-tests/`.
- Put mock/fake CLI coverage under `tests/mock-cli-tests/`.
- Keep `README.md`, `docs/`, and `CHANGELOG.md` in sync with user-facing changes.

## Automation

- Browser auth must delegate credentials/session state/CSRF to ChatLogin; the host only retains the legacy configuration-key cookie envelope and separate API/executor gates.
- Run `python -m pytest -q` with Node.js 22+ on PATH (or set `NODE_BINARY`) for the frontend fetch runtime regression. CI installs Node.js and treats its absence as a failure.
- The normal suite includes a real TCP login smoke on a random loopback port, synthetic credentials/workspace and bounded startup/shutdown; it never calls a model or launches an executor.

- Keep automation small and reviewable.
- Prefer commands that can run in CI without interactive prompts.
- Ensure generated defaults are safe for local development.
