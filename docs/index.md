# ChatBoard 文档

这里收纳 `ChatBoard` 的长期维护文档。

## 主题

- [CLI 文档](cli.md)：命令树、副作用边界、`ensure` 与 workspace/card 推导规则。

## 项目入口

[GitHub 项目](https://github.com/ChatArch/ChatBoard){ .md-button .md-button--primary }
[English Docs](https://arch.gh.wzhecnu.cn/ChatBoard/en/){ .md-button }

## Web UI

- 主看板右上角的 Settings 可以把当前站点作为本会话 backend，也可以保存其他 ChatBoard API backend URL 和可选 API token。
- 如果一个 backend 需要被其他站点上的 ChatBoard 前端读取，应在该 backend 服务端配置 `CHATBOARD_CORS_ORIGINS` 允许对应前端来源。

## 本地预览

```bash
pip install -e ".[docs]"
mkdocs serve
```

英文版见：https://arch.gh.wzhecnu.cn/ChatBoard/en/
