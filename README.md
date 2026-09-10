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

## 快速开始

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

## CLI 文档

`chatbd` 是 ChatBoard 的辅助管理 CLI。Web UI 是主要产品形态；当前 CLI 只保留 Project 的只读投影、metadata maintenance 和规范化 lifecycle 操作。运行 `chatbd --tree` 可从真实 Click 注册树输出带参数签名的命令面，`chatbd --tree-brief` 输出相同命令面但省略参数签名。两者都由 ChatStyle 共享 runtime 渲染。长期文档见 https://arch.gh.wzhecnu.cn/ChatBoard/cli/：

- 命令树、`--tree` / `--tree-brief` 回读和命令副作用边界。
- `ensure` 创建 `card.md` 的推导规则。
- area、stage、id、title、summary、tags、links 等 metadata 的符号逻辑。
- Discussion、Archive、Discard 和底层 card move 的移动规则。
- `chatbd serve` 的可选登录门禁：`--username`、`--password`、`--password-file`、`CHATBOARD_USERNAME` 和 `CHATBOARD_PASSWORD`；生产/共享环境优先用 ChatEnv，而不是手写 `~/.config` 文件。
- ChatEnv 对齐：`CHATBOARD_SERVICE_URL`、`CHATBOARD_HOME`、`CHATBOARD_BACKENDS_FILE`、`CHATBOARD_USERNAME` / `CHATBOARD_PASSWORD`、`CHATBOARD_API_KEY`、default backend token 分层管理；ChatEnv profile 默认在 `~/.chatarch/envs/Chatboard/`，ChatBoard runtime state 默认在 `~/.chatarch/chatboard/`。
- API 自动化可用 Bearer / `X-ChatBoard-Token`，登录 cookie 可通过 `chatenv token refresh Chatboard <profile>` 写入 runtime token store；`chatbd paths` 可只读回捞当前 ChatEnv/ChatArch-owned 路径和配置开关。
- Web 看板的 card 日期/描述/摘要展示。
- 新增独立 `Tasks` tab：`type: task` 的任务卡片与原有 Projects 看板分开展示。
- 任务管理 CLI：`chatbd project task create/list/status/update/transition/delete`，覆盖创建、查看状态、更新、阶段迁移和软删除。

## 0.2.0 登录与认证

登录后端与登录页复用 ChatLogin；保留可选账号、共享密码及独立 API/executor token，不引入多用户业务权限。会话持久化在 ChatBoard runtime root 的 `sessions.sqlite3`，由 ChatLogin 负责过期、容量限制与撤销。

- 升级后旧 cookie 需重新登录一次。`CHATBOARD_AUTH_SECRET` 优先、否则复用密码的签名密钥语义不变；轮换有效密钥立即拒绝旧 cookie。
- 浏览器 cookie 写请求必须同时携带同源 `Origin` 和 `X-CSRF-Token`；先用同一个 cookie 读取 `GET /api/session`，取返回的 `csrf_token`。官方前端自动处理。
- Bearer / `X-ChatBoard-Token` 自动化无需浏览器 CSRF；真实 executor 操作仍需独立执行 token。
- `CHATBOARD_LOGIN_PALETTE`、`CHATBOARD_LOGIN_LAYOUT`、`CHATBOARD_LOGIN_APPEARANCE` 可定制共享登录页。

详见[登录与认证文档](https://arch.gh.wzhecnu.cn/ChatBoard/auth/)。CI 的常规 pytest 包含完整认证回归、有界 loopback HTTP 登录/退出和 Node.js 前端 fetch 测试。

## 目录结构

- `src/`：包源码
- `tests/code-tests/`：代码测试和历史测试迁移
- `tests/cli-tests/`：真实 CLI 测试，doc-first
- `tests/mock-cli-tests/`：mock/fake CLI 测试，doc-first
- `docs/`：长期维护文档，由 mkdocs 构建

## 开发说明

扩展脚手架前，先阅读 `DEVELOP.md` 和 `AGENTS.md`。
