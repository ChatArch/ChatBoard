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
chatbd --version
chatbd project catalog
python -m pytest -q
python -m build
```

## CLI 文档

`chatbd` 是 ChatBoard 的辅助管理 CLI。Web UI 是主要产品形态；当前 CLI 只保留 Project 的只读投影、metadata maintenance 和规范化 lifecycle 操作。运行 `chatbd --tree` 可从真实 Click 注册树输出当前命令面。长期文档见 https://arch.gh.wzhecnu.cn/ChatBoard/cli/：

- 命令树、`--tree` 回读和命令副作用边界。
- `ensure` 创建 `card.md` 的推导规则。
- area、stage、id、title、summary、tags、links 等 metadata 的符号逻辑。
- Discussion、Archive、Discard 和底层 card move 的移动规则。
- `chatbd serve` 的可选登录门禁：`--username`、`--password`、`--password-file`、`CHATBOARD_USERNAME` 和 `CHATBOARD_PASSWORD`。
- ChatEnv 对齐：`CHATBOARD_SERVICE_URL`、`CHATBOARD_USERNAME` / `CHATBOARD_PASSWORD` 和 `CHATBOARD_API_KEY` 分层管理；API 自动化可用 Bearer / `X-ChatBoard-Token`，登录 cookie 可通过 `chatenv token refresh Chatboard <profile>` 写入 runtime token store。
- Web 看板的 card 日期/描述/摘要展示。
- 新增独立 `Tasks` tab：`type: task` 的任务卡片与原有 Projects 看板分开展示。
- 任务管理 CLI：`chatbd project task create/list/status/update/transition/delete`，覆盖创建、查看状态、更新、阶段迁移和软删除。

## 目录结构

- `src/`：包源码
- `tests/code-tests/`：代码测试和历史测试迁移
- `tests/cli-tests/`：真实 CLI 测试，doc-first
- `tests/mock-cli-tests/`：mock/fake CLI 测试，doc-first
- `docs/`：长期维护文档，由 mkdocs 构建

## 开发说明

扩展脚手架前，先阅读 `DEVELOP.md` 和 `AGENTS.md`。
