from pathlib import Path

from click.testing import CliRunner

from chatboard.cli import main


def _first_text_block_after(text: str, heading: str) -> str:
    section_start = text.index(heading)
    block_start = text.index("```text\n", section_start) + len("```text\n")
    block_end = text.index("\n```", block_start)
    return text[block_start:block_end]


def test_mkdocs_material_i18n_public_domain_and_icon_renderer():
    mkdocs = Path("mkdocs.yml").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "site_url: https://arch.gh.wzhecnu.cn/ChatBoard/" in mkdocs
    assert "repo_url: https://github.com/ChatArch/ChatBoard" in mkdocs
    assert "name: material" in mkdocs
    assert "- i18n:" in mkdocs
    assert "docs_structure: suffix" in mkdocs
    assert "mkdocs-static-i18n" in pyproject
    assert "mkdocs-material>=9.5,<9.7" in pyproject
    assert "pymdownx.emoji" in mkdocs
    assert "material.extensions.emoji.twemoji" in mkdocs
    assert "material.extensions.emoji.to_svg" in mkdocs


def test_cli_docs_are_bilingual_and_use_public_command():
    zh = Path("docs/cli.md").read_text(encoding="utf-8")
    en = Path("docs/cli.en.md").read_text(encoding="utf-8")

    assert "chatbd --tree" in zh
    assert "chatbd --tree" in en
    assert "chatbd --tree-brief" in zh
    assert "chatbd --tree-brief" in en
    assert "python -m chatboard.cli" not in zh
    assert "python -m chatboard.cli" not in en


def test_bilingual_cli_tree_blocks_match_registered_runtime():
    result = CliRunner().invoke(main, ["--tree"])
    zh = Path("docs/cli.md").read_text(encoding="utf-8")
    en = Path("docs/cli.en.md").read_text(encoding="utf-8")

    assert result.exit_code == 0, result.output
    assert _first_text_block_after(zh, "## 命令树") == result.output.strip()
    assert _first_text_block_after(en, "## CLI Tree") == result.output.strip()


def test_cli_runtime_dependencies_match_chatarch_standard():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert '"chatstyle>=0.2.0,<0.3.0"' in pyproject
    assert '"chatenv>=0.2.11,<0.3.0"' in pyproject


def test_docs_home_links_to_public_docs_and_github_project():
    zh = Path("docs/index.md").read_text(encoding="utf-8")
    en = Path("docs/index.en.md").read_text(encoding="utf-8")

    assert "https://github.com/ChatArch/ChatBoard" in zh
    assert "https://github.com/ChatArch/ChatBoard" in en
    assert "https://arch.gh.wzhecnu.cn/ChatBoard/en/" in zh
    assert "https://arch.gh.wzhecnu.cn/ChatBoard/" in en
