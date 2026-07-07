# Changelog

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
