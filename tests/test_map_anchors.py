"""Behaviour of the anchor-fragment mapper."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import DocsRepo

from halos_docs_tools import map_anchors


def built(repo: DocsRepo, relative: str, *ids: str) -> Path:
    """A built page carrying the given heading ids, in order."""
    headings = "".join(f'<h2 id="{i}">{i}</h2>' for i in ids)
    return repo.write(f"site/{relative}", f"<html><body>{headings}</body></html>")


def site_with_two_pages(repo: DocsRepo, translated_ids: tuple[str, ...]) -> None:
    """docs/{en,fi}/{index,guide}.md, built, with fi headings renamed."""
    repo.source("guide.md")
    repo.translation("fi", "guide.md")
    built(repo, "index.html", "intro")
    built(repo, "guide/index.html", "setup", "wiring")
    built(repo, "fi/index.html", "johdanto")
    built(repo, "fi/guide/index.html", *translated_ids)


def run(*argv: str) -> int:
    return map_anchors.main(list(argv))


def test_english_fragment_is_rewritten_to_the_translated_slug(
    docs_repo: DocsRepo, capsys
):
    site_with_two_pages(docs_repo, ("asennus", "johdotus"))
    docs_repo.write("docs/fi/index.md", "Katso [ohjeet](guide.md#wiring).\n")
    assert run("site", "fi", "--apply") == 0
    assert "#johdotus" in (docs_repo.root / "docs/fi/index.md").read_text()
    assert "1 anchors rewritten" in capsys.readouterr().out


def test_without_apply_it_reports_but_does_not_write(docs_repo: DocsRepo, capsys):
    site_with_two_pages(docs_repo, ("asennus", "johdotus"))
    docs_repo.write("docs/fi/index.md", "Katso [ohjeet](guide.md#wiring).\n")
    assert run("site", "fi") == 0
    assert "#wiring" in (docs_repo.root / "docs/fi/index.md").read_text()
    assert "1 anchors to rewrite" in capsys.readouterr().out


def test_fragment_already_matching_is_left_alone(docs_repo: DocsRepo, capsys):
    site_with_two_pages(docs_repo, ("setup", "wiring"))
    docs_repo.write("docs/fi/index.md", "Katso [ohjeet](guide.md#wiring).\n")
    assert run("site", "fi", "--apply") == 0
    assert "0 anchors rewritten" in capsys.readouterr().out


def test_structure_mismatch_is_reported_rather_than_mapped_wrongly(
    docs_repo: DocsRepo, capsys
):
    site_with_two_pages(docs_repo, ("asennus",))  # one heading, English has two
    docs_repo.write("docs/fi/index.md", "Katso [ohjeet](guide.md#wiring).\n")
    assert run("site", "fi", "--apply") == 1
    out = capsys.readouterr().out
    assert "structure differs" in out
    assert "2 headings in en, 1 translated" in out
    assert "#wiring" in (docs_repo.root / "docs/fi/index.md").read_text()


def test_external_links_are_left_alone(docs_repo: DocsRepo, capsys):
    site_with_two_pages(docs_repo, ("asennus", "johdotus"))
    docs_repo.write(
        "docs/fi/index.md", "Katso [muualta](https://example.invalid/#wiring).\n"
    )
    assert run("site", "fi", "--apply") == 0
    assert "0 anchors rewritten" in capsys.readouterr().out


def test_unbuilt_page_is_an_error_not_a_silent_skip(docs_repo: DocsRepo):
    docs_repo.source("guide.md")
    built(docs_repo, "index.html", "intro")
    built(docs_repo, "fi/index.html", "johdanto")
    with pytest.raises(SystemExit, match="build the site first"):
        run("site", "fi")


def test_default_locale_comes_from_mkdocs_not_from_a_hard_coded_en(
    docs_repo: DocsRepo, capsys
):
    """The package cannot assume the default locale is English."""
    docs_repo.write(
        "mkdocs.yml",
        """\
        site_name: Test docs
        plugins:
          - i18n:
              docs_structure: folder
              languages:
                - locale: fi
                  name: Suomi
                  default: true
                - locale: en
                  name: English
        """,
    )
    (docs_repo.root / "docs/en/index.md").unlink()
    (docs_repo.root / "docs/fi/index.md").unlink()
    docs_repo.write("docs/fi/guide.md", "# Ohje\n")
    docs_repo.write("docs/en/guide.md", "Katso [ohjeet](guide.md#johdotus).\n")
    built(docs_repo, "guide/index.html", "asennus", "johdotus")
    built(docs_repo, "en/guide/index.html", "setup", "wiring")
    assert run("site", "en", "--apply") == 0
    assert "#wiring" in (docs_repo.root / "docs/en/guide.md").read_text()
