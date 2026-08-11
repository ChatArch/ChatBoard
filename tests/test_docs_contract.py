from pathlib import Path


def test_mkdocs_material_i18n_public_domain_and_icon_renderer():
    mkdocs = Path("mkdocs.yml").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "site_url: https://arch.gh.wzhecnu.cn/ChatBoard/" in mkdocs
    assert "repo_url: https://github.com/ChatArch/ChatBoard" in mkdocs
    assert "name: material" in mkdocs
    assert "- i18n:" in mkdocs
    assert "docs_structure: suffix" in mkdocs
    assert "mkdocs-static-i18n" in pyproject
    assert "mkdocs-material>=9.5,<10.0" in pyproject
    assert "pymdownx.emoji" in mkdocs
    assert "material.extensions.emoji.twemoji" in mkdocs
    assert "material.extensions.emoji.to_svg" in mkdocs


def test_cli_docs_are_bilingual_and_use_public_command():
    zh = Path("docs/cli.md").read_text(encoding="utf-8")
    en = Path("docs/cli.en.md").read_text(encoding="utf-8")

    assert "chatbd --tree" in zh
    assert "chatbd --tree" in en
    assert "python -m chatboard.cli" not in zh
    assert "python -m chatboard.cli" not in en
