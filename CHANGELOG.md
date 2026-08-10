# Changelog

## Unreleased

## 0.1.5 - 2026-08-10

### Added

- 新增顶层 `chatbd --tree`，从真实 Click 注册树输出命令树、参数签名和用途注释。

### Changed

- 补齐 `--tree`、中英文 CLI 文档和 README 回读说明。
- 对齐 ChatArch 内部依赖窗口：`chatenv>=0.2.3,<0.3.0`、`chatstyle>=0.1.1,<0.2.0`。
- 对齐 MkDocs/i18n 文档构建依赖和 Preview Docs 公网域名链接。

## 0.1.4 - 2026-08-05

### Fixed

- Point documentation metadata, MkDocs canonical URL, and README docs badges to the enabled GitHub Pages custom domain.

## 0.1.3 - 2026-08-05

### Added

- Add an optional `chatbd serve` account/password login gate for the Web UI and workspace APIs.
- Add card date, description, summary, and date-grouped dashboard rendering.
- Add a Machines page backed by workspace-local `.chatboard/machines.json` inventory data when explicitly enabled.

### Changed

- Replace the flat `chatboard` CLI with the focused `chatbd project ...` management tree.
- Resolve the default workspace from ChatEnv `CHATBOARD_WORKSPACE_ROOT`.
- Keep `scan` and `catalog` read-only; metadata creation is explicit through `project card ensure`.
- Remove low-frequency Discussion metadata, Archive readiness, and standalone Trash commands from the public CLI.
- Use ChatStyle schemas and the shared `-i/-I` interaction contract for required management inputs.
- Preflight move destinations before writing metadata so conflicts leave source Projects unchanged.
- Show the default Web board as a four-step lifecycle: `想法`、`进行中`、`归档中`、`已归档`; hide Discard from the main board projection.
- Keep the Machines page as an empty placeholder unless `CHATBOARD_ENABLE_MACHINES=true` is set.

## 0.1.2 - 2026-07-07

### Added

- Add paginated column loading so the board renders progressively on large workspaces.
- Add an IDE-style read-only Files explorer with lazy directory loading and text preview.
- Add task-focused file browsing with a `Show all` mode for all non-ignored files.

### Changed

- Centralize initial ChatBoard default ignore rules for gitignore-style noise.

## 0.1.1 - 2026-07-07

### Added

- Add workspace `card.md` frontmatter storage as the card metadata source of truth.
- Add Discussion topic creation and project-to-Discussion `Items/` routing.
- Add card detail tabs, Files browser, file preview APIs, and fullscreen modal flow.
- Add Archive month/day grouping and Discard area support for soft-deleted tasks.

### Changed

- Treat workspace paths as structural truth for card area and lifecycle placement.
- Scan nested `projects/<topic>/MM-DD-*` task directories while ignoring topic index roots.

### Removed

- Remove legacy `card.json` sidecar compatibility and writes.

## YYYY-MM-DD

### Added

### Changed

### Fixed
