# ChatBoard Docs

Long-lived documentation for `ChatBoard` lives here.

## Topics

- [CLI reference](cli.md): command tree, side effects, and `ensure` derivation rules.

## Project Links

[GitHub Project](https://github.com/ChatArch/ChatBoard){ .md-button .md-button--primary }
[Chinese Docs](https://arch.gh.wzhecnu.cn/ChatBoard/){ .md-button }

## Web UI

- The Settings button in the board header can use this site as the session backend or save other ChatBoard API backend URLs with optional API tokens.
- A backend that should be read from another ChatBoard frontend origin must opt in with `CHATBOARD_CORS_ORIGINS`.

## Local Preview

```bash
pip install -e ".[docs]"
mkdocs serve
```

Chinese version: https://arch.gh.wzhecnu.cn/ChatBoard/
