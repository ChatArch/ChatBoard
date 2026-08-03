<div align="center">
    <a href="https://pypi.python.org/pypi/ChatBoard">
        <img src="https://img.shields.io/pypi/v/ChatBoard.svg" alt="PyPI version" />
    </a>
    <a href="https://github.com/ChatArch/ChatBoard/actions/workflows/ci.yml">
        <img src="https://github.com/ChatArch/ChatBoard/actions/workflows/ci.yml/badge.svg" alt="Tests" />
    </a>
    <a href="https://ChatArch.github.io/ChatBoard">
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
chatbd --version
chatbd project catalog
python -m pytest -q
python -m build
```

## CLI 文档

`chatbd` 是 ChatBoard 的辅助管理 CLI。Web UI 是主要产品形态；当前 CLI 只保留 Project 的只读投影、metadata maintenance 和规范化 lifecycle 操作。长期文档见 `docs/cli.md`：

- 命令树与命令副作用边界。
- `ensure` 创建 `card.md` 的推导规则。
- area、stage、id、title、summary、tags、links 等 metadata 的符号逻辑。
- Discussion、Archive、Discard 和底层 card move 的移动规则。
- `chatbd serve` 的可选登录门禁：`--username`、`--password`、`--password-file`、`CHATBOARD_USERNAME` 和 `CHATBOARD_PASSWORD`。
- Web 看板的 card 日期/描述/摘要展示，以及 workspace-local `.chatboard/machines.json` 驱动的 Machines 页面。

## 目录结构

- `src/`：包源码
- `tests/code-tests/`：代码测试和历史测试迁移
- `tests/cli-tests/`：真实 CLI 测试，doc-first
- `tests/mock-cli-tests/`：mock/fake CLI 测试，doc-first
- `docs/`：长期维护文档，由 mkdocs 构建

## 开发说明

扩展脚手架前，先阅读 `DEVELOP.md` 和 `AGENTS.md`。
