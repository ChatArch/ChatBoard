# CLI Docs

`chatbd` is ChatBoard's auxiliary management entry point. The Web UI is the primary product surface; the CLI keeps stable Project projections, metadata maintenance, and lifecycle operations that are easy to get wrong by hand.

## CLI Tree

Run `chatbd --tree` to have ChatStyle print the command surface with parameter signatures from the actual Click registry. `chatbd --tree-brief` prints the same hierarchy and purposes without signatures. This page should stay aligned with the runtime output.

```text
chatbd
├── --help  # Show this message and exit.
├── --version  # Show the version and exit.
├── --tree  # Print the registered CLI tree and exit.
├── --tree-brief  # Print the registered CLI tree without parameter signatures and exit.
├── project  # Inspect and manage ChatArch workspace Projects.
│   ├── archive  # Archive completed Project cards.
│   │   └── run [CARD-ID] [--dry-run] [--interactive]  # Move a Project card into the dated archive area.
│   ├── card  # Inspect and move Project cards.
│   │   ├── ensure [PROJECT-PATH] [--interactive]  # Create card.md metadata for an existing Project if missing.
│   │   ├── move [CARD-ID] [AREA] [--stage STAGE] [--dry-run] [--interactive]  # Move a Project card between workspace areas.
│   │   └── show [CARD-ID] [--interactive]  # Show the detail projection for a Project card.
│   ├── catalog  # Print the Project board catalog grouped by columns.
│   ├── discard [CARD-ID] [--reason REASON] [--dry-run] [--interactive]  # Move a Project card into the formal Discard area.
│   ├── discussion  # Create Discussion topics and add Project items.
│   │   ├── add-item [DISCUSSION-ID] [CARD-ID] [--dry-run] [--interactive]  # Move a Project card into a Discussion topic's Items directory.
│   │   └── create [TITLE] [--slug SLUG] [--interactive]  # Create a project-like Discussion topic.
│   ├── scan  # Scan the workspace and list Project cards without writing metadata.
│   └── task  # Manage Tasks shown on the Tasks board tab.
│       ├── create [TITLE] [--description DESCRIPTION] [--topic TOPIC] [--slug SLUG] [--source-platform SOURCE-PLATFORM] [--source-url SOURCE-URL] [--accept-mode ACCEPT-MODE] [--side-effect-level SIDE-EFFECT-LEVEL] [--next-action NEXT-ACTION] [--assignee ASSIGNEE] [--tag TAGS] [--dry-run] [--interactive]  # Create a Task card and task project skeleton.
│       ├── delete [CARD-ID] [--reason REASON] [--dry-run] [--interactive]  # Soft-delete a Task card into the formal Discard area.
│       ├── list  # Print the Tasks board grouped by task stages.
│       ├── status [CARD-ID] [--interactive]  # Show a Task card's current status and available transitions.
│       ├── transition [CARD-ID] [TRANSITION] [--reason REASON] [--need NEED] [--summary SUMMARY] [--stage STAGE] [--interactive]  # Move a Task card between task stages.
│       └── update [CARD-ID] [--title TITLE] [--description DESCRIPTION] [--summary SUMMARY] [--next-action NEXT-ACTION] [--accept-mode ACCEPT-MODE] [--side-effect-level SIDE-EFFECT-LEVEL] [--assignee ASSIGNEE] [--tag TAGS] [--interactive]  # Update Task metadata.
└── serve [--host HOST] [--port PORT] [--root ROOT] [--reload] [--username USERNAME] [--password PASSWORD] [--password-file PASSWORD-FILE]  # Start the ChatBoard web UI.
```

## Command Layers

| Layer | Commands | Main purpose | Default side effects |
| --- | --- | --- | --- |
| Board runtime | `serve` | Start the Web UI | No |
| Read projection | `project scan`, `project catalog`, `project card show` | Read workspace state and print JSON | No |
| Task management | `project task create/list/status/update/transition/delete` | Manage task cards in the separate Tasks tab | `list/status` no; others yes |
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

## Tasks Tab and Task Management

The Tasks tab is a separate task board; it does not replace the legacy Projects tab:

- `project scan`, `project catalog`, and `/api/catalog` continue to project legacy Project cards.
- `type: task` cards appear in the Web `Tasks` tab, `GET /api/tasks`, and `chatbd project task list`.
- Task cards still write a workspace project skeleton so `PRD.md`, `progress.md`, `reports/`, and `card.md` remain available.

Create a task:

```bash
chatbd project task create "Board task CLI" \
  --topic chatarch \
  --slug 08-12-board-task-cli \
  --description "Create and manage a task from CLI." \
  --source-platform feishu \
  --source-url https://example.feishu.cn/thread/cli \
  --accept-mode accept \
  --side-effect-level local_write \
  --next-action "Accept from CLI." \
  --tag board \
  --tag cli
```

Inspect and move task stages:

```bash
chatbd project task list
chatbd project task status CARD_ID
chatbd project task update CARD_ID --next-action "Worker can start." --accept-mode auto
chatbd project task transition CARD_ID accept --reason "ready"
chatbd project task transition CARD_ID block --reason "needs examples" --need "choose three cards"
chatbd project task transition CARD_ID move --stage review --reason "needs human check"
chatbd project task delete CARD_ID --reason "example cleanup" --dry-run
```

Task columns are:

```text
Inbox -> Ready -> Running -> Blocked -> Review -> Done
```

`Auto` is not a column; it is task metadata: `accept_mode: accept | auto`.
Side-effect risk is stored in `side_effect_level`: `read_only`, `local_write`, `external_write`, `infra`, or `irreversible`.

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

## ChatEnv and Access Tokens

`chatbd serve` still supports direct login flags:

```bash
chatbd serve --username admin@example.com --password "[REDACTED]"
chatbd serve --password-file ~/.config/chatboard/password
```

For shared ChatArch environments, prefer a ChatEnv profile so service address, workspace root, browser login credentials, and automation API token stay separated:

```bash
cat <<'EOF' | chatenv paste --profile ops --yes --stdin
CHATBOARD_SERVICE_URL=https://board.public.wzhecnu.cn/
CHATBOARD_WORKSPACE_ROOT=~/Playground
CHATBOARD_USERNAME=admin@example.com
CHATBOARD_PASSWORD='[REDACTED]'
CHATBOARD_API_KEY='[REDACTED]'
EOF
chatenv use ops -t Chatboard
chatbd serve
```

Access-control layers:

- `CHATBOARD_USERNAME` / `CHATBOARD_PASSWORD`: browser login. `POST /api/login` returns an `HttpOnly` session cookie.
- `CHATBOARD_API_KEY`: non-browser automation for CLI runners and webhooks. Workspace APIs accept `Authorization: Bearer ...` or `X-ChatBoard-Token` without first creating a browser session.
- Stable ChatEnv profiles live under `envs/Chatboard/<profile>.env`; runtime cookies/tokens live under `tokens/Chatboard/<profile>.json` via `chatenv token ...`. Do not commit or document raw token values.

Refresh a browser-login cookie into ChatEnv's runtime token store:

```bash
chatenv token refresh Chatboard ops
```

Long-lived API tokens can be imported through ChatEnv's explicit JSON import flow, for example `{"api_key":"[REDACTED]"}`. ChatEnv status output only shows safe metadata, not token values.

## Boundaries

- `scan`, `catalog`, and `card show` are read-only projections.
- `card ensure`, `discussion create/add-item`, `archive run`, `discard`, and `card move` can write or move files.
- `serve` can expose a local Web UI and optional login gate, but it does not mutate Project metadata by itself.
- ChatBoard does not provide a generic workspace delete command. Trash is a deliberate lifecycle move.
