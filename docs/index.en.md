# ChatBoard Docs

Long-lived documentation for `ChatBoard` lives here.

## Topics

- [CLI reference](cli.md): command tree, side effects, and `ensure` derivation rules.

## Project Links

[GitHub Project](https://github.com/ChatArch/ChatBoard){ .md-button .md-button--primary }
[Chinese Docs](https://arch.gh.wzhecnu.cn/ChatBoard/){ .md-button }

## Web UI

- The Settings button in the board header manages backend profiles through the same-origin server-side proxy; browsers select only profile ids and never directly access backend URLs or store/send backend tokens.
- The backend registry and proxy tokens should be managed through ChatEnv / `~/.chatarch`: the default registry is `~/.chatarch/chatboard/backends.json`, with `CHATBOARD_BACKENDS_FILE` as an explicit override.

## Local Preview

```bash
pip install -e ".[docs]"
mkdocs serve
```

Chinese version: https://arch.gh.wzhecnu.cn/ChatBoard/
