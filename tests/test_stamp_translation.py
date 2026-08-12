"""Behaviour of the stamping command."""

from __future__ import annotations

import pytest
from conftest import DocsRepo

from halos_docs_tools import stamp_translation, translation_status


def run(*argv: str) -> int:
    return stamp_translation.main(list(argv))


def state(repo: DocsRepo, language: str, page: str) -> str:
    default, languages = translation_status.configured_languages()
    entries = translation_status.collect(default, languages, want_diff=False)
    return next(
        e.state for e in entries if e.language == language and e.page == page
    )


def test_stamping_a_stale_translation_makes_it_current(docs_repo: DocsRepo):
    docs_repo.source("index.md", "# Title\n\nRevised.\n")
    assert state(docs_repo, "fi", "index.md") == "stale"
    assert run("docs/fi/index.md") == 0
    assert state(docs_repo, "fi", "index.md") == "current"


def test_stamping_an_unstamped_translation_adds_frontmatter(docs_repo: DocsRepo):
    docs_repo.translation("fi", "index.md", stamp=None)
    assert run("docs/fi/index.md") == 0
    text = (docs_repo.root / "docs/fi/index.md").read_text()
    assert text.startswith("---\ntranslated_from: ")
    assert state(docs_repo, "fi", "index.md") == "current"


def test_stamping_preserves_other_frontmatter_keys(docs_repo: DocsRepo):
    docs_repo.write(
        "docs/fi/index.md",
        """\
        ---
        title: Otsikko
        translated_from: 0000000000000000000000000000000000000000
        ---

        Body.
        """,
    )
    assert run("docs/fi/index.md") == 0
    text = (docs_repo.root / "docs/fi/index.md").read_text()
    assert "title: Otsikko" in text
    assert "0000000" not in text
    assert text.count("translated_from:") == 1


def test_stamping_several_pages_at_once(docs_repo: DocsRepo):
    docs_repo.source("index.md", "# Title\n\nRevised.\n")
    assert run("docs/fi/index.md", "docs/sv/index.md") == 0
    assert state(docs_repo, "fi", "index.md") == "current"
    assert state(docs_repo, "sv", "index.md") == "current"


def test_path_outside_a_language_directory_is_rejected(docs_repo: DocsRepo):
    docs_repo.write("notes.md", "Body.\n")
    with pytest.raises(SystemExit, match="not a path under"):
        run("notes.md")


def test_stamping_a_source_page_is_rejected(docs_repo: DocsRepo):
    with pytest.raises(SystemExit, match="source page"):
        run("docs/en/index.md")


def test_translation_without_an_english_source_is_rejected(docs_repo: DocsRepo):
    docs_repo.translation("fi", "orphan.md", stamp=None)
    with pytest.raises(SystemExit, match="no English source"):
        run("docs/fi/orphan.md")


def test_nonexistent_path_is_rejected(docs_repo: DocsRepo):
    with pytest.raises(SystemExit, match="does not exist"):
        run("docs/fi/nope.md")
