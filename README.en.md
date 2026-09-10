<div align="center">
    <a href="https://pypi.python.org/pypi/ChatBoard">
        <img src="https://img.shields.io/pypi/v/ChatBoard.svg" alt="PyPI version" />
    </a>
    <a href="https://github.com/ChatArch/ChatBoard/actions/workflows/ci.yml">
        <img src="https://github.com/ChatArch/ChatBoard/actions/workflows/ci.yml/badge.svg" alt="Tests" />
    </a>
    <a href="https://arch.gh.wzhecnu.cn/ChatBoard/">
        <img src="https://img.shields.io/badge/docs-mkdocs-blue.svg" alt="Documentation" />
    </a>
</div>

<div align="center">

[English](README.en.md) | [简体中文](README.md)
</div>

# ChatBoard

ChatBoard: ChatArch kanban board tooling package

## Quick Start

```bash
pip install -e ".[dev]"
chatbd --help
chatbd --tree
chatbd --tree-brief
chatbd --version
chatbd project catalog
python -m pytest -q
python -m build
```

## CLI Docs

`chatbd` is ChatBoard's auxiliary management CLI. The Web UI remains the primary product surface; the CLI keeps only Project read projections, metadata maintenance, and standardized lifecycle operations. Run `chatbd --tree` for the registered command surface with parameter signatures, or `chatbd --tree-brief` for the same surface without signatures. ChatStyle's shared runtime renders both. See https://arch.gh.wzhecnu.cn/ChatBoard/en/cli/ for:

- Command tree, `--tree` / `--tree-brief` readback, and side-effect boundaries.
- `ensure` rules for creating `card.md` files.
- Metadata derivation for area, stage, id, title, summary, tags, and links.
- Movement rules for Discussion, Archive, Discard, and low-level card moves.
- Optional `chatbd serve` login gate via `--username`, `--password`, `--password-file`, `CHATBOARD_USERNAME`, and `CHATBOARD_PASSWORD`.
- ChatEnv alignment: keep `CHATBOARD_SERVICE_URL`, `CHATBOARD_USERNAME` / `CHATBOARD_PASSWORD`, and `CHATBOARD_API_KEY` as separate layers; API automation can use Bearer / `X-ChatBoard-Token`, while browser-login cookies can be refreshed into the runtime token store with `chatenv token refresh Chatboard <profile>`.
- Card date/description/summary rendering.
- A separate `Tasks` tab for `type: task` cards, kept out of the legacy Projects board projection.
- Task-management CLI: `chatbd project task create/list/status/update/transition/delete` for task creation, status, updates, stage transitions, and soft-delete.

## 0.2.0 Login and Authentication

ChatLogin supplies the credential adapter, session engine and shared login UI. Optional username/shared password and separate API/executor tokens remain; no multi-user business permissions are added. ChatLogin owns expiry, capacity and revocation in `sessions.sqlite3` under the ChatBoard runtime root.

- Old cookies require one new login after upgrade. Signing-key precedence remains `CHATBOARD_AUTH_SECRET`, then the password; rotating the effective key immediately rejects old cookies.
- Cookie-authenticated writes require both a same-origin `Origin` and `X-CSRF-Token`. Read `GET /api/session` with the same cookie to obtain `csrf_token`; the built-in frontend handles this automatically.
- Bearer / `X-ChatBoard-Token` automation needs no browser CSRF; real executor operations still require their separate privileged token.
- Customize the shared UI with `CHATBOARD_LOGIN_PALETTE`, `CHATBOARD_LOGIN_LAYOUT` and `CHATBOARD_LOGIN_APPEARANCE`.

See [Login and Authentication](https://arch.gh.wzhecnu.cn/ChatBoard/en/auth/). Normal pytest/CI includes full auth regressions, a bounded loopback HTTP login/logout smoke and Node.js frontend fetch tests.

## Layout

- `src/`: package source code
- `tests/code-tests/`: code tests and migrated historical tests
- `tests/cli-tests/`: real CLI tests, doc-first
- `tests/mock-cli-tests/`: mock/fake CLI tests, doc-first
- `docs/`: long-lived project docs built by mkdocs

## Development Notes

See `DEVELOP.md` and `AGENTS.md` before expanding the scaffold.
