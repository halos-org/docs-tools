"""Behaviour of the translation status report."""

from __future__ import annotations

import pytest
from conftest import MKDOCS_NO_I18N, MKDOCS_ONLY_DEFAULT, DocsRepo

from halos_docs_tools import translation_status


def run(*argv: str) -> int:
    return translation_status.main(list(argv))


def states(repo: DocsRepo) -> dict[tuple[str, str], str]:
    default, languages = translation_status.configured_languages()
    entries = translation_status.collect(default, languages, want_diff=False)
    return {(e.language, e.page): e.state for e in entries}


def test_matching_stamp_reports_current(docs_repo: DocsRepo):
    assert states(docs_repo)[("fi", "index.md")] == "current"


def test_absent_translation_reports_missing(docs_repo: DocsRepo):
    docs_repo.source("guide.md")
    assert states(docs_repo)[("fi", "guide.md")] == "missing"


def test_translation_without_frontmatter_reports_unstamped(docs_repo: DocsRepo):
    docs_repo.translation("fi", "index.md", stamp=None)
    assert states(docs_repo)[("fi", "index.md")] == "unstamped"


def test_stamp_behind_the_source_reports_stale(docs_repo: DocsRepo):
    docs_repo.source("index.md", "# Title\n\nEnglish body, revised.\n")
    assert states(docs_repo)[("fi", "index.md")] == "stale"


def test_translation_whose_source_was_deleted_reports_orphaned(docs_repo: DocsRepo):
    (docs_repo.root / "docs/en/index.md").unlink()
    assert states(docs_repo)[("fi", "index.md")] == "orphaned"


def test_one_locale_stale_does_not_affect_the_others(docs_repo: DocsRepo):
    docs_repo.source("index.md", "# Title\n\nRevised.\n")
    docs_repo.translation("sv", "index.md")
    assert states(docs_repo)[("fi", "index.md")] == "stale"
    assert states(docs_repo)[("sv", "index.md")] == "current"


def test_no_translation_locales_configured_says_so(docs_repo: DocsRepo, capsys):
    docs_repo.write("mkdocs.yml", MKDOCS_ONLY_DEFAULT)
    assert run() == 0
    assert "No translation languages configured." in capsys.readouterr().out


def test_missing_i18n_plugin_is_an_error_not_an_empty_success(docs_repo: DocsRepo):
    docs_repo.write("mkdocs.yml", MKDOCS_NO_I18N)
    with pytest.raises(SystemExit, match="no i18n plugin"):
        run()


def test_unreachable_stamped_blob_omits_the_diff_and_hints(docs_repo: DocsRepo, capsys):
    # A well-formed hash of an object no clone has. An all-digit stamp would
    # not do: YAML reads it as a number, and `translated_from: 000...0` then
    # reports unstamped rather than stale.
    absent = "deadbeef" * 5
    docs_repo.translation("fi", "index.md", stamp=absent)
    docs_repo.translation("sv", "index.md", stamp=absent)
    assert run("--format", "markdown", "--diff") == 0
    out = capsys.readouterr().out
    assert "fetch-depth: 0" in out
    assert "```diff" not in out


def test_diff_shows_the_english_change_since_the_translation(docs_repo: DocsRepo, capsys):
    docs_repo.commit("docs: seed")
    docs_repo.source("index.md", "# Title\n\nEnglish body, revised.\n")
    assert run("--format", "markdown", "--diff") == 0
    out = capsys.readouterr().out
    assert "+English body, revised." in out


def test_only_pages_narrows_the_detail_but_not_the_summary(docs_repo: DocsRepo, capsys):
    docs_repo.source("guide.md")
    docs_repo.source("index.md", "# Title\n\nRevised.\n")
    assert run("--format", "markdown", "--only-pages", "guide.md") == 0
    out = capsys.readouterr().out
    assert "`guide.md`" in out
    assert "| `index.md` |" not in out
    # The per-locale summary still counts every page, filtered or not.
    assert "**fi** — 1 stale, 1 missing" in out
    assert "**sv** — 1 stale, 1 missing" in out


def test_text_format_lists_every_page_that_is_not_current(docs_repo: DocsRepo, capsys):
    docs_repo.source("guide.md")
    assert run() == 0
    out = capsys.readouterr().out
    assert "missing   guide.md" in out
    assert "current=1" in out
