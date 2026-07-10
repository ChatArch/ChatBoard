# CLI 文档

`chatbd` CLI 是 ChatBoard 的辅助管理入口。Web UI 是主要产品形态；CLI 只保留稳定、常用且容易因路径规则出错的 Project 操作。

## 命令树

```text
chatbd
├── serve [--host HOST] [--port PORT] [--reload]
└── project
    ├── scan
    ├── catalog
    ├── card
    │   ├── ensure PROJECT_PATH
    │   ├── show CARD_ID
    │   └── move CARD_ID AREA [--stage STAGE] [--dry-run]
    ├── discussion
    │   ├── create TITLE [--slug SLUG]
    │   └── add-item DISCUSSION_ID CARD_ID [--dry-run]
    ├── archive
    │   └── run CARD_ID [--dry-run]
    └── discard CARD_ID --reason TEXT [--dry-run]
```

## 命令分层

| 层级 | 命令 | 主要用途 | 默认副作用 |
| --- | --- | --- | --- |
| Board runtime | `serve` | 启动 Web UI | 否 |
| Read projection | `project scan`、`project catalog`、`project card show` | 读取 workspace 并输出 JSON | 否 |
| Metadata maintenance | `project card ensure` | 为已有目录补齐 `card.md` | 是 |
| Discussion workflow | `project discussion create/add-item` | 创建 Discussion 节点、迁入 review item | 是 |
| Lifecycle workflow | `project archive run`、`project discard`、`project card move` | 移动 workspace item | 是 |

`--dry-run` 只存在于移动类命令。带 `--dry-run` 时，命令返回预计路径和 metadata，不移动目录。

需要参数的命令使用 ChatStyle 统一输入解析：参数缺失且当前终端可交互时会自动补问，`-i` 强制交互，`-I` 禁止交互并快速失败。参数完整时仍按普通 CLI 方式直接执行。

## Workspace 根目录

新 CLI 不提供 `--root` 或 `--workspace`。ChatBoard 通过 ChatEnv 字段 `CHATBOARD_WORKSPACE_ROOT` 读取 workspace 根目录，缺省值为：

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
if area == trash or stage == trashed:      trash
elif area == discard or stage == discarded: discard
elif area == archive:                       archive
elif area == discussion:                    discussion
else:                                       project
```

默认 UI 列是：

```text
Project
Discussion
Archive
Discard
```

`trash` 不在默认列中，但仍可作为底层 card area 被识别。

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

开发时可加：

```bash
chatbd serve --reload
```

## 使用建议

- 日常查看 workspace 状态：优先使用 Web UI 或 `chatbd project catalog`。
- 补齐 board metadata：显式使用 `chatbd project card ensure PROJECT_PATH`。
- 所有移动类命令先使用 `--dry-run` 检查目标路径。
- Discussion 决策等自由文本直接维护在 Project 文档中，不为低频 metadata 更新单独提供 CLI。
