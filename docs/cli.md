# CLI 文档

`chatbd` CLI 是 ChatBoard 的辅助管理入口。Web UI 是主要产品形态；CLI 只保留稳定、常用且容易因路径规则出错的 Project 操作。

## 命令树

运行 `chatbd --tree` 会通过 ChatStyle 从实际 Click 注册树输出带参数签名的当前命令面；`chatbd --tree-brief` 输出相同层级和用途，但省略参数签名。文档中的树应与运行态命令保持一致。

```text
chatbd
├── --help  # Show this message and exit.
├── --version  # Show the version and exit.
├── --tree  # Print the registered CLI tree and exit.
├── --tree-brief  # Print the registered CLI tree without parameter signatures and exit.
├── paths  # Print ChatEnv and ChatArch-owned ChatBoard runtime paths.
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

## 命令分层

| 层级 | 命令 | 主要用途 | 默认副作用 |
| --- | --- | --- | --- |
| Board runtime | `serve` | 启动 Web UI | 否 |
| Runtime readback | `paths` | 只读输出 ChatEnv provider 目录和 ChatArch-owned runtime/state 路径 | 否 |
| Read projection | `project scan`、`project catalog`、`project card show` | 读取 workspace 并输出 JSON | 否 |
| Task management | `project task create/list/status/update/transition/delete` | 管理独立 Tasks tab 中的任务卡片 | `list/status` 否；其余是 |
| Metadata maintenance | `project card ensure` | 为已有目录补齐 `card.md` | 是 |
| Discussion workflow | `project discussion create/add-item` | 创建 Discussion 节点、迁入 review item | 是 |
| Lifecycle workflow | `project archive run`、`project discard`、`project card move` | 移动 workspace item | 是 |

`--dry-run` 只存在于移动类命令。带 `--dry-run` 时，命令返回预计路径和 metadata，不移动目录。

需要参数的命令使用 ChatStyle 统一输入解析：参数缺失且当前终端可交互时会自动补问，`-i` 强制交互，`-I` 禁止交互并快速失败。参数完整时仍按普通 CLI 方式直接执行。

## Workspace 根目录

Project 管理命令不提供 `--root` 或 `--workspace`。ChatBoard 通过 ChatEnv 字段 `CHATBOARD_WORKSPACE_ROOT` 读取 workspace 根目录，缺省值为：

```text
~/Playground
```

ChatBoard 扫描以下 workspace area：

```text
projects/
discussion/
archive/
discard/
```

`trash` area 的实际路径不是 `trash/`，而是：

```text
.trash/chatboard/
```

Trash 是底层文件安全缓冲，不提供独立 CLI；必要时显式使用 `chatbd project card move CARD_ID trash`。

扫描时会跳过常见构建、依赖和缓存目录，例如 `.git`、`.venv`、`node_modules`、`dist`、`build`、`site`、`playground`、`.trash`。

## Card 候选目录

ChatBoard 把满足以下谓词的目录视为 card 候选：

```text
is_card_dir(path) :=
  path 是目录
  AND path 不在忽略目录中
  AND 存在任一文件：PRD.md OR progress.md OR card.md
```

默认扫描不会把 `discussion/<topic>/Items/<item>` 当作顶层 card 输出。它们会作为 discussion card 的 `nested_items` 展示。

## Tasks tab 与任务管理

Tasks tab 是独立任务看板，不替代原有 Projects tab：

- `project scan`、`project catalog` 和 `/api/catalog` 继续只投影原有 Project card。
- `type: task` 的卡片只出现在 Web `Tasks` tab、`GET /api/tasks` 和 `chatbd project task list`。
- Task card 仍写入 workspace project skeleton，便于继续使用 `PRD.md`、`progress.md`、`reports/` 和 `card.md`。

任务创建示例：

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

任务状态和阶段迁移：

```bash
chatbd project task list
chatbd project task status CARD_ID
chatbd project task update CARD_ID --next-action "Worker can start." --accept-mode auto
chatbd project task transition CARD_ID accept --reason "ready"
chatbd project task transition CARD_ID block --reason "needs examples" --need "choose three cards"
chatbd project task transition CARD_ID move --stage review --reason "needs human check"
chatbd project task delete CARD_ID --reason "example cleanup" --dry-run
```

Tasks tab 的阶段列为：

```text
Inbox -> Ready -> Running -> Blocked -> Review -> Done
```

其中 `Auto` 不是列，而是 task metadata：`accept_mode: accept | auto`。
风险/副作用级别写入 `side_effect_level`，当前取值为：`read_only`、`local_write`、`external_write`、`infra`、`irreversible`。

## `card.md` 的角色

`card.md` 是 ChatBoard 的 board metadata sidecar。它不是 workspace 基础协议的必需文件，但一旦存在，ChatBoard 会优先读取它。

`card.md` 保存有限 frontmatter：

```yaml
---
schema: chatboard.project_card.v1
id: projects-example
title: Example
area: project
stage: development
tags:
  - chatarch
accept_mode: accept
side_effect_level: local_write
next_action: Review task status.
source:
  platform: feishu
  url: https://example.feishu.cn/thread/...
assets:
  prd: PRD.md
  progress: progress.md
  reports_dir: reports
links:
  feishu:
    - https://example.feishu.cn/docx/...
---

# Summary

Short human-readable summary.
```

注意：frontmatter 中 `area: project` 会被读成内部 area `projects`；保存时也会把 `projects` 写回为 `project`，让 card 内容更接近人类语义。

## `ensure` 符号逻辑

`ensure` 的语义是“确保某个 workspace item 有可持久化的 board card”。它不是强制重写。

```text
ensure_card(path, root):
  if path/card.md exists:
    return load_card(path, root)
  else:
    card = infer_card(path, root)
    save path/card.md
    return card
```

因此：

- 已存在 `card.md` 时，`ensure` 读取现有 metadata，不覆盖正文。
- 不存在 `card.md` 时，`ensure` 从目录结构和常用文件推导 metadata，并创建 `card.md`。
- 如果目标在 `discussion/` 下，返回值会补充 `nested_items`，也就是 `Items/` 下的 review item 摘要。

### ID 推导

Card ID 来自 workspace 相对路径：

```text
relative_path = path 相对 root 的路径
id = slugify(relative_path)
```

`slugify` 规则：

```text
把非 a-z / A-Z / 0-9 的字符替换为 -
去掉首尾 -
转小写
空结果回退为 workspace-card
```

示例：

| workspace path | card id |
| --- | --- |
| `projects/07-08-chatboard-cli-tree-review` | `projects-07-08-chatboard-cli-tree-review` |
| `discussion/07-08-board-next/Items/foo` | `discussion-07-08-board-next-items-foo` |

### Area 推导

Area 来自 workspace 相对路径的第一段：

| 路径前缀 | area |
| --- | --- |
| `projects/` | `projects` |
| `discussion/` | `discussion` |
| `archive/` | `archive` |
| `discard/` | `discard` |
| `.trash/` | `trash` |
| 其他路径 | `projects` |

### Stage 推导

当没有 `card.md` 时，stage 按以下顺序推导：

```text
if area == archive:    archived
elif area == discard:  discarded
elif area == discussion: review
elif PRD.md 不存在:    scaffold
elif progress.md 不存在: prd
else:                  development
```

当存在 `card.md` 时，stage 以 frontmatter 中的 `stage` 为准。

### Title 推导

Title 优先来自 `PRD.md` 中第一个一级标题：

```text
# Some Title
```

如果没有一级标题，则从目录名推导：

```text
07-08-chatboard-cli-tree-review -> Chatboard Cli Tree Review
```

### Summary 推导

Summary 来自 `PRD.md` 中第一条非空、非标题、非列表的正文行，最多保留 240 字符。没有可用正文时为空；保存 `card.md` 时正文 fallback 为 `TODO`。

### Tags 推导

Tags 来自 workspace 相对路径中的中间目录：

```text
tags = relative_path.parts[:-1]
       去掉 projects / discussion / archive / Items
       最多保留 6 个
```

这使主题分组目录可以自然成为 board filter。

### Links 推导

`ensure` 会检查 `PRD.md` 和 `progress.md`：

- 如果文件存在，写入 `assets.prd` / `assets.progress`。
- 如果正文中出现包含 `feishu` 的 URL，写入 `links.feishu`。
- 如果存在 `reports/`，最多收集 50 个 report 文件，并写入 `assets.reports_dir: reports`。

## `project scan` 与 `project catalog`

`project scan` 输出扁平 card 列表：

```bash
chatbd project scan
```

`project catalog` 输出按 board column 聚合后的 JSON：

```bash
chatbd project catalog
```

两条命令都是只读操作。缺少 `card.md` 时会临时推导 metadata，但不会写入 sidecar；需要持久化 metadata 时应显式使用 `project card ensure`。

Column 规则：

```text
if area == trash or stage == trashed:          trash      # 底层状态，不在默认 UI 列中
elif area == discard or stage == discarded:    discard    # 底层状态，不在默认 UI 列中
elif area == archive or stage == archived:     archive    # 已归档
elif area == discussion:                       thoughts   # 想法
elif area == projects and stage in
     {archive_ready, complete, postprocess}:   archiving  # 归档中
else:                                          project    # 进行中
```

默认 UI 列是：

```text
想法
进行中
归档中
已归档
```

`discard` 和 `trash` 仍可作为底层 card area 被识别，但不在主看板列中展示。

## `project card ensure`

为已有 Project 目录创建缺失的 `card.md`：

```bash
chatbd project card ensure ~/Playground/projects/example
```

已有 `card.md` 时只读取，不强制覆盖正文。

## `project card show`

根据 `CARD_ID` 查找目录并输出 detail projection：

```bash
chatbd project card show projects-07-08-chatboard-cli-tree-review
```

输出包含 overview、files、PRD、progress、discussion、artifacts 和 archive sections。

## `project card move`

通用 area 移动命令：

```bash
chatbd project card move CARD_ID archive --dry-run
```

目标 area 可为：

```text
projects | discussion | archive | discard | trash
```

默认目标路径规则：

| area | destination |
| --- | --- |
| `projects` | `projects/<原相对路径去掉第一段>` |
| `discussion` | `discussion/<原相对路径去掉第一段>` |
| `discard` | `discard/<原相对路径去掉第一段>` |
| `archive` | `archive/YYYY-MM-DD/<原相对路径去掉第一段>` |
| `trash` | `.trash/chatboard/<UTC-like stamp>/<原相对路径去掉第一段>` |

默认 stage 规则：

| area | stage |
| --- | --- |
| `projects` | `development` |
| `discussion` | `review` |
| `archive` | `archived` |
| `discard` | `discarded` |
| `trash` | `trashed` |

可以用 `--stage` 覆盖默认 stage。若目标路径已存在，命令失败，不覆盖。

## Discussion 命令

### `project discussion create`

创建标准的 project-like Discussion topic：

```bash
chatbd project discussion create "Board Next"
```

创建内容：

```text
discussion/<MM-DD-name>/
  PRD.md
  progress.md
  card.md
  Items/
```

### `project discussion add-item`

把一个 Project 移动到 Discussion 的 `Items/`：

```bash
chatbd project discussion add-item DISCUSSION_ID CARD_ID --dry-run
```

`DISCUSSION_ID` 必须指向 Discussion card，目标已存在时失败，不覆盖。

## Archive / Discard 命令

### `project archive run`

```bash
chatbd project archive run CARD_ID --dry-run
```

把 card 移入 `archive/YYYY-MM-DD/...` 并将 stage 设置为 `archived`。

### `project discard`

```bash
chatbd project discard CARD_ID --reason "superseded" --dry-run
```

记录 discard reason，并把 Project 移入正式的 `discard/` area。Discard 是生命周期结果；Trash 只是底层安全缓冲，因此没有独立 `trash` 命令。

## Serve 命令

```bash
chatbd serve --host 127.0.0.1 --port 8000
```

`serve --root PATH` 会为当前服务进程设置 `CHATBOARD_WORKSPACE_ROOT`。

默认不启用登录，适合只绑定 `127.0.0.1` 的本地开发场景。

需要给 Web UI 和 API 加登录门禁时，启动时提供密码：

```bash
chatbd serve --username admin@example.com --password '[REDACTED]'
```

更推荐用 ChatEnv profile，避免密码进入 shell history，也避免服务配置散落到非 ChatArch 目录。ChatBoard 的 canonical ChatEnv provider 是 `Chatboard`，默认文件位于 `~/.chatarch/envs/Chatboard/<profile>.env`：

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

如果确实要用 `--password-file` 做本机临时入口，密码文件也应放在 ChatArch-owned runtime root，例如 `~/.chatarch/chatboard/secrets/password`；不要使用 `~/.config/chatboard-*` 或仓库/project 目录保存秘密。

只读回捞当前路径和配置开关：

```bash
chatbd paths
```

默认路径：

```text
ChatEnv profile:      ~/.chatarch/envs/Chatboard/<profile>.env
ChatBoard state root: ~/.chatarch/chatboard/
Backend registry:     ~/.chatarch/chatboard/backends.json
Runtime token store:  ~/.chatarch/tokens/Chatboard/<profile>.json
```

ChatBoard 同时注册了 ChatEnv schema，可把服务地址、workspace root、登录账号、登录密码、自动化 API token、backend registry 和 server-side proxy token 分开保存到 ChatEnv profile。

分层语义：

- `CHATBOARD_USERNAME` / `CHATBOARD_PASSWORD`：面向浏览器登录，`POST /api/login` 成功后写入 `HttpOnly` session cookie。
- `CHATBOARD_API_KEY`：面向 CLI、runner、Webhook 等非浏览器自动化，可通过 `Authorization: Bearer ...` 或 `X-ChatBoard-Token` 调用 workspace API，不需要先拿浏览器 cookie。
- ChatEnv 的稳定 profile 放在 `envs/Chatboard/<profile>.env`；运行态登录 cookie/token 应通过 `chatenv token ...` 放在 `tokens/Chatboard/<profile>.json`，不要把 token 明文写入文档或 commit。

示例：刷新指定 profile 的浏览器登录 cookie 到 ChatEnv runtime token store：

```bash
chatenv token refresh Chatboard ops
```

如果只需要把长期 API token 作为运行态 token 管理，可以用 ChatEnv 的显式 import 流程导入 JSON，例如 `{"api_key":"[REDACTED]"}`；命令输出只显示安全 metadata，不回显 token 值。

启用后：

- 未登录访问 `/` 会跳转到 `/login`。
- 未登录访问 workspace API 会返回 `401`。
- `/api/health` 和 `/api/auth` 保持公开，方便健康检查和登录页判断状态。
- 登录会写入 `HttpOnly` session cookie。
- `POST /api/logout` 会清除 session cookie。
- 已配置 `CHATBOARD_API_KEY` 时，workspace API 也接受 `Authorization: Bearer ...` 或 `X-ChatBoard-Token`；`/api/auth` 只返回 `api_token_enabled`，不会回显 token。

可选环境变量：

| 变量 | 作用 |
| --- | --- |
| `CHATBOARD_USERNAME` | 可选登录账号；设置后登录必须同时匹配账号和密码 |
| `CHATBOARD_PASSWORD` | 启用登录并设置登录密码 |
| `CHATBOARD_SERVICE_URL` | ChatEnv 中记录的 ChatBoard 服务基地址，供 token refresh / 外部调用使用 |
| `CHATBOARD_HOME` | ChatBoard runtime/state root；默认 `~/.chatarch/chatboard` |
| `CHATBOARD_BACKENDS_FILE` | server-side backend registry JSON；默认 `~/.chatarch/chatboard/backends.json` |
| `CHATBOARD_REGISTRY_TOKEN` | 保护 backend profile 注册/写入的 server-side token |
| `CHATBOARD_DEFAULT_BACKEND_TOKEN` | default backend API token；只由 server-side proxy 使用 |
| `CHATBOARD_API_KEY` | 自动化 API token；支持 Bearer / `X-ChatBoard-Token` 调用 workspace API |
| `CHATBOARD_AUTH_SECRET` | session cookie 签名密钥；默认复用登录密码 |
| `CHATBOARD_SESSION_TTL_SECONDS` | session 有效期，默认 12 小时，最小 60 秒 |
| `CHATBOARD_COOKIE_SECURE` | 为 `1/true/yes/on` 时设置 Secure cookie |

通过 HTTPS 反向代理公开服务时，应启用 `CHATBOARD_COOKIE_SECURE`，并在反向代理层为登录接口配置请求限速。这个可选门禁用于小规模 ChatBoard 部署，不替代 SSO 或 MFA。

开发时可加：

```bash
chatbd serve --reload
```

## 使用建议

- 日常查看 workspace 状态：优先使用 Web UI 或 `chatbd project catalog`。
- 补齐 board metadata：显式使用 `chatbd project card ensure PROJECT_PATH`。
- 所有移动类命令先使用 `--dry-run` 检查目标路径。
- Discussion 决策等自由文本直接维护在 Project 文档中，不为低频 metadata 更新单独提供 CLI。
