# ChatBoard 文档

这里收纳 `ChatBoard` 的长期维护文档。

## 主题

- [CLI 文档](cli.md)：命令树、副作用边界、`ensure` 与 workspace/card 推导规则。

## 项目入口

[GitHub 项目](https://github.com/ChatArch/ChatBoard){ .md-button .md-button--primary }
[English Docs](https://arch.gh.wzhecnu.cn/ChatBoard/en/){ .md-button }

## Web UI

- 主看板右上角的 Settings 通过同源 server-side proxy 管理 backend profiles；浏览器只选择 profile id，不直接访问 backend URL，也不会保存或发送 backend token。
- backend registry 和 proxy token 应通过 ChatEnv / `~/.chatarch` 管理：默认 registry 为 `~/.chatarch/chatboard/backends.json`，可用 `CHATBOARD_BACKENDS_FILE` 显式覆盖。

## 本地预览

```bash
pip install -e ".[docs]"
mkdocs serve
```

英文版见：https://arch.gh.wzhecnu.cn/ChatBoard/en/
