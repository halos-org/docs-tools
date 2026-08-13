"""The blocking mode: when the translation status check fails a build.

The invariant is a property of the repository, not of a pull request's diff,
so the gate looks at every page in every configured locale whatever the report
above it was asked to show.
"""

from __future__ import annotations

from conftest import DocsRepo

from halos_docs_tools import translation_status


def run(*argv: str) -> int:
    return translation_status.main(list(argv))


def test_a_fully_current_repository_passes(docs_repo: DocsRepo):
    assert run("--check") == 0


def test_stale_fails(docs_repo: DocsRepo):
    docs_repo.source("index.md", "# Title\n\nRevised.\n")
    assert run("--check") != 0


def test_missing_fails(docs_repo: DocsRepo):
    docs_repo.source("guide.md")
    assert run("--check") != 0


def test_unstamped_fails(docs_repo: DocsRepo):
    docs_repo.translation("fi", "index.md", stamp=None)
    assert run("--check") != 0


def test_orphaned_fails(docs_repo: DocsRepo):
    docs_repo.write("docs/fi/gone.md", "---\ntranslated_from: x\n---\n\nBody.\n")
    assert run("--check") != 0


def test_one_locale_behind_is_enough_to_fail(docs_repo: DocsRepo):
    docs_repo.source("index.md", "# Title\n\nRevised.\n")
    docs_repo.translation("fi", "index.md")  # fi brought current, sv left behind
    assert run("--check") != 0


def test_only_pages_does_not_narrow_what_the_gate_considers(docs_repo: DocsRepo):
    """The report may be filtered. The gate may not."""
    docs_repo.source("guide.md")  # missing in both locales
    docs_repo.source("index.md", "# Title\n\nRevised.\n")  # stale in both
    assert run("--check", "--format", "markdown", "--only-pages", "index.md") != 0


def test_without_the_flag_a_failing_repository_still_exits_zero(docs_repo: DocsRepo):
    docs_repo.source("index.md", "# Title\n\nRevised.\n")
    assert run() == 0
    assert run("--format", "markdown") == 0


def test_the_failure_names_every_page_and_locale_responsible(
    docs_repo: DocsRepo, capsys
):
    docs_repo.source("guide.md")
    docs_repo.source("index.md", "# Title\n\nRevised.\n")
    assert run("--check") != 0
    out = capsys.readouterr().out
    for locale in ("fi", "sv"):
        assert f"{locale}/guide.md" in out
        assert f"{locale}/index.md" in out
    assert "missing" in out
    assert "stale" in out


def test_the_failure_names_entries_the_filtered_report_omitted(
    docs_repo: DocsRepo, capsys
):
    """A red check whose comment never mentions the offending page is worse
    than no check: the reader cannot act on it."""
    docs_repo.source("guide.md")
    assert run("--check", "--format", "markdown", "--only-pages", "index.md") != 0
    out = capsys.readouterr().out
    assert "fi/guide.md" in out


def test_a_page_with_another_markdown_extension_is_checked(docs_repo: DocsRepo):
    """mkdocs publishes .markdown, .mdown, .mkdn and .mkd as well as .md.

    A source page the checker does not enumerate is served in every locale
    with the default language's content while the gate reports missing=0.
    """
    docs_repo.write("docs/en/guide.markdown", "# Guide\n\nBody.\n")
    assert run("--check") != 0


def test_a_page_under_a_symlinked_directory_is_checked(docs_repo: DocsRepo):
    """mkdocs walks the docs tree with followlinks=True; rglob does not."""
    shared = docs_repo.root / "shared_pages"
    shared.mkdir()
    (shared / "wiring.md").write_text("# Wiring\n\nBody.\n", encoding="utf-8")
    (docs_repo.root / "docs/en/shared").symlink_to(shared)
    assert run("--check") != 0


def test_markdown_outside_every_configured_locale_stops_the_check(
    docs_repo: DocsRepo, capsys
):
    """mkdocs-static-i18n serves a root-level page under every locale.

    The checker cannot tell whether such a page needs translating, so it says
    so rather than passing over it.
    """
    docs_repo.write("docs/safety.md", "# Safety\n\nBody.\n")
    assert run("--check") == 2
    out = capsys.readouterr().out
    assert "docs/safety.md" in out
    assert "cannot classify" in out


def test_no_source_pages_is_not_a_pass(docs_repo: DocsRepo, capsys):
    """A gate that fails open on a misconfiguration is the worst outcome."""
    for page in (docs_repo.root / "docs/en").rglob("*.md"):
        page.unlink()
    assert run("--check") == 2
    assert "no source pages" in capsys.readouterr().out


def test_no_configured_locales_is_not_a_pass_under_check(docs_repo: DocsRepo, capsys):
    from conftest import MKDOCS_ONLY_DEFAULT

    docs_repo.write("mkdocs.yml", MKDOCS_ONLY_DEFAULT)
    assert run("--check") == 2
    assert "No translation languages configured." in capsys.readouterr().out
