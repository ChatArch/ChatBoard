# CLI Docs

`chatbd` is ChatBoard's auxiliary management entry point. The Web UI is the primary product surface; the CLI keeps stable Project projections, metadata maintenance, and lifecycle operations that are easy to get wrong by hand.

## CLI Tree

Run `chatbd --tree` to print the command surface from the actual Click registry. This page should stay aligned with that runtime output.

```text
chatbd  # Run the ChatBoard web app and Project management tools.
├── --help  # Show this help message.
├── --version  # Show the installed package version.
├── --tree  # Print the registered command tree.
├── serve [--host <HOST>] [--port <PORT>] [--root <ROOT>] [--reload] [--username <USERNAME>] [--password <PASSWORD>] [--password-file <PASSWORD-FILE>]  # Start the ChatBoard web UI.
└── project  # Inspect and manage ChatArch workspace Projects.
    ├── scan  # Scan the workspace and list Project cards without writing metadata.
    ├── catalog  # Print the Project board catalog grouped by columns.
    ├── card  # Inspect and move Project cards.
    │   ├── ensure [<PROJECT-PATH>] [--interactive]  # Create card.md metadata for an existing Project if missing.
    │   ├── show [<CARD-ID>] [--interactive]  # Show the detail projection for a Project card.
    │   └── move [<CARD-ID>] [<AREA>] [--stage <STAGE>] [--dry-run] [--interactive]  # Move a Project card between workspace areas.
    ├── discussion  # Create Discussion topics and add Project items.
    │   ├── create [<TITLE>] [--slug <SLUG>] [--interactive]  # Create a project-like Discussion topic.
    │   └── add-item [<DISCUSSION-ID>] [<CARD-ID>] [--dry-run] [--interactive]  # Move a Project card into a Discussion topic's Items directory.
    ├── archive  # Archive completed Project cards.
    │   └── run [<CARD-ID>] [--dry-run] [--interactive]  # Move a Project card into the dated archive area.
    └── discard [<CARD-ID>] [--reason <REASON>] [--dry-run] [--interactive]  # Move a Project card into the formal Discard area.
```

## Command Layers

| Layer | Commands | Main purpose | Default side effects |
| --- | --- | --- | --- |
| Board runtime | `serve` | Start the Web UI | No |
| Read projection | `project scan`, `project catalog`, `project card show` | Read workspace state and print JSON | No |
| Metadata maintenance | `project card ensure` | Create `card.md` for an existing directory | Yes |
| Discussion workflow | `project discussion create/add-item` | Create Discussion nodes and move review items | Yes |
| Lifecycle workflow | `project archive run`, `project discard`, `project card move` | Move workspace items | Yes |

`--dry-run` exists only on move-style commands. With `--dry-run`, the command returns the planned destination and metadata without moving directories.

Commands with required inputs use ChatStyle input resolution: complete argv runs directly; missing recoverable arguments can prompt in an interactive terminal; `-i` forces prompting; `-I` disables prompting and fails fast.

## Workspace Root

Project management commands do not accept `--root` or `--workspace`. ChatBoard reads the workspace root from the ChatEnv field `CHATBOARD_WORKSPACE_ROOT`; the default is:

```text
~/Playground
```

ChatBoard scans these workspace areas:

```text
projects/
discussion/
archive/
discard/
```

The trash area is stored under `.trash/chatboard/`. There is no standalone Trash CLI; use `chatbd project card move CARD_ID trash` when an explicit card move is needed.

## Card Metadata

`card.md` is ChatBoard's board metadata sidecar. It is not required by the workspace protocol, but ChatBoard reads it first when it exists.

`project card ensure` means "make sure this workspace item has durable board metadata". It reads an existing `card.md` without overwriting its body; otherwise it infers metadata from the directory structure and common files, then writes a new card.

Important derived fields:

| Field | Source |
| --- | --- |
| `id` | Workspace-relative path slug |
| `area` | First path segment: `projects`, `discussion`, `archive`, `discard`, or `.trash` |
| `stage` | Archive/discard/discussion status or PRD/progress presence |
| `title` | First H1 in `PRD.md`, falling back to the directory name |
| `summary` | First non-empty body line in `PRD.md` |
| `tags` | Topic path segments between the area and item directory |
| `links.feishu` | Feishu URLs found in `PRD.md` / `progress.md` |

## Boundaries

- `scan`, `catalog`, and `card show` are read-only projections.
- `card ensure`, `discussion create/add-item`, `archive run`, `discard`, and `card move` can write or move files.
- `serve` can expose a local Web UI and optional login gate, but it does not mutate Project metadata by itself.
- ChatBoard does not provide a generic workspace delete command. Trash is a deliberate lifecycle move.
