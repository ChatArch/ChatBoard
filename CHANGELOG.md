# Changelog

## Unreleased

## 0.1.11 - 2026-08-26

### Added

- Add executor capability and run lifecycle APIs for Codex, Cursor Agent, and OpenCode discovery, dry-run/mock run metadata, log polling, resume/stop/collect controls, and read-only Web visibility.
- Add `CHATBOARD_EXECUTOR_API_KEY` as a separate privileged token for real executor operations.
- Add `/api/resolve-path` and executor `public_links` metadata so backend-local workspace paths can be mapped to shareable ChatBoard API URLs when a card-scoped route is available.
- Add explicit ChatBoard task and PRD link contracts for assignment posts, including `task_link`, `prd_link`, `GET /api/tasks/{card_id}`, and the `/#/tasks/{card_id}` Web deep link.

## 0.1.10 - 2026-08-22

### Added

- Add a server-side backend profile store and proxy so the browser selects backend profiles without receiving backend API tokens.
- Support a unique, user-changeable default backend for new sessions, plus session-only current backend switching in Settings.
- Add server-side backend profile management with redacted token status in Settings; profile edits use the existing authenticated frontend session rather than a separate management token.
- Add `CHATBOARD_HOME` and `chatbd paths` so operators can verify ChatEnv provider storage and ChatArch-owned runtime paths without printing secrets.

### Changed

- Route board API calls through `/api/backends/{profile}/api/...` so backend URLs are resolved by the frontend/proxy service host.
- Require `chatenv>=0.2.11,<0.3.0` so ChatBoard reuses ChatEnv's owner read/write profile-file mode instead of setting permissions itself.

## 0.1.9 - 2026-08-21

### Added

- Add a Web Settings backend switcher so one ChatBoard frontend can read the current site or saved remote API backends for the browser session.
- Inject the default backend profile from ChatEnv/runtime config and keep configured backend tokens masked in Settings.

### Changed

- Support opt-in cross-origin backend access with `CHATBOARD_CORS_ORIGINS`.

### Fixed

- Keep `/assets/*` public while auth is enabled so the login page and board load CSS/JS instead of redirected HTML.
- Make the Settings modal resilient to invalid saved backend entries so the dialog can still open and reset them.
- Add explicit CSS/JS asset cache busting and resource-nav fallback styling so updated resource cards do not render as default blue links after deploy.

## 0.1.8 - 2026-08-21

### Added

- Add draggable board column resizing with browser-local persistence and double-click reset.
- Add `chatbd --tree-brief` for a compact signature-free view of the registered command surface.

### Changed

- Fix the default Projects board column weights so an empty `想法` / `thoughts` column no longer receives the largest track.
- Replace ChatBoard's package-local CLI tree renderer with ChatStyle `add_tree_option()`.
- Align runtime dependencies to `chatstyle>=0.2.0,<0.3.0` and `chatenv>=0.2.10,<0.3.0`.
- Keep docs builds on the supported `mkdocs-material>=9.5,<9.7` compatibility window.

## 0.1.7 - 2026-08-21

### Added

- Add a separate Tasks board tab and task card metadata (`type: task`, source, accept mode, side-effect level, and next action) without changing the legacy Projects board projection.
- Add task-management REST APIs: `/api/pages`, `/api/tasks`, `/api/tasks/{id}/status`, `/api/tasks/{id}/transitions`, and task soft-delete.
- Add `chatbd project task create/list/status/update/transition/delete` for task CRUD, status inspection, stage migration, and soft-delete.
- Add ChatEnv-aligned access control fields (`CHATBOARD_SERVICE_URL`, username/password, API key) and a `chatenv token refresh Chatboard <profile>` runtime token provider for browser-login cookies.
- Add Docs and GitHub resource links to the board, login page, and MkDocs home pages.

### Changed

- Keep `project scan`, `project catalog`, and `/api/catalog` focused on legacy Project cards; task cards are listed through the new Tasks tab/API/CLI.
- Accept the Authorization header and `X-ChatBoard-Token` for workspace API automation when `CHATBOARD_API_KEY` is configured.
- Style public resource links as subtle glass cards so they fit the warm ChatBoard UI without competing with primary actions.

### Removed

- Remove the duplicate Machines page, machine inventory API, and workspace-local `.chatboard/machines.json` integration from ChatBoard; machine status now belongs in ChatGlance.

## 0.1.6 - 2026-08-12

### Changed

- Keep `chatbd --tree` rooted at the public console command name even when invoked through `python -m chatboard.cli`.
- Enable the MkDocs Material emoji renderer (`pymdownx.emoji` with Material `twemoji`/`to_svg`) for bilingual public docs.
- Harden tag-driven PyPI publishing with package-version, default-branch, and PyPI exact-version guards.
- Add CI smoke checks for installed `chatbd --version` and `chatbd --tree`, plus distribution metadata checks.

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
