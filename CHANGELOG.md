# Changelog

## Unreleased

### Added

- Add an optional `chatbd serve` account/password login gate for the Web UI and workspace APIs.
- Add card date, description, summary, and date-grouped dashboard rendering.
- Add a Machines page backed by workspace-local `.chatboard/machines.json` inventory data.

### Changed

- Replace the flat `chatboard` CLI with the focused `chatbd project ...` management tree.
- Resolve the default workspace from ChatEnv `CHATBOARD_WORKSPACE_ROOT`.
- Keep `scan` and `catalog` read-only; metadata creation is explicit through `project card ensure`.
- Remove low-frequency Discussion metadata, Archive readiness, and standalone Trash commands from the public CLI.
- Use ChatStyle schemas and the shared `-i/-I` interaction contract for required management inputs.
- Preflight move destinations before writing metadata so conflicts leave source Projects unchanged.
- Sort paginated card columns before slicing so page boundaries remain stable.

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
