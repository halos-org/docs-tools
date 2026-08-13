"""Behaviour of the built-site anchor checker."""

from __future__ import annotations

from pathlib import Path

from conftest import DocsRepo

from halos_docs_tools import check_anchors


def page(site: Path, relative: str, body: str) -> Path:
    path = site / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
    return path


def run(*argv: str) -> int:
    return check_anchors.main(list(argv))


def test_resolving_anchors_pass(tmp_path: Path, capsys):
    site = tmp_path / "site"
    page(site, "index.html", '<h2 id="intro">Intro</h2><a href="guide/#setup">go</a>')
    page(site, "guide/index.html", '<h2 id="setup">Setup</h2>')
    assert run(str(site)) == 0
    assert "All anchors resolve." in capsys.readouterr().out


def test_missing_anchor_on_the_target_page_fails(tmp_path: Path, capsys):
    site = tmp_path / "site"
    page(site, "index.html", '<a href="guide/#nope">go</a>')
    page(site, "guide/index.html", '<h2 id="setup">Setup</h2>')
    assert run(str(site)) == 1
    out = capsys.readouterr().out
    assert "index.html" in out
    assert "#nope" in out
    assert "no such anchor" in out


def test_link_to_a_page_that_does_not_exist_fails(tmp_path: Path, capsys):
    site = tmp_path / "site"
    page(site, "index.html", '<a href="ghost/#setup">go</a>')
    assert run(str(site)) == 1
    assert "target page does not exist" in capsys.readouterr().out


def test_links_without_fragments_and_external_links_are_ignored(tmp_path: Path, capsys):
    site = tmp_path / "site"
    page(
        site,
        "index.html",
        '<a href="guide/">go</a>'
        '<a href="https://example.invalid/#x">out</a>'
        '<a href="mailto:a@example.invalid">mail</a>',
    )
    page(site, "guide/index.html", "<p>Guide</p>")
    assert run(str(site)) == 0
    assert "Checked 0 anchor links" in capsys.readouterr().out


def test_empty_site_directory_is_not_a_pass(tmp_path: Path, capsys):
    empty = tmp_path / "site"
    empty.mkdir()
    assert run(str(empty)) == 2
    assert "nothing to check" in capsys.readouterr().err


def test_excluded_page_contributes_no_links(tmp_path: Path, capsys):
    """The case measured on docs.halos.fi: a generated single-page export.

    Every one of its 690 broken fragments came from mkdocs-print-site-plugin
    output, and none from a content page.
    """
    site = tmp_path / "site"
    page(site, "index.html", '<h2 id="intro">Intro</h2>')
    page(site, "print_page/index.html", '<a href="../#nope">broken</a>')
    assert run(str(site)) == 1
    assert run(str(site), "--exclude", "print_page/*") == 0


def test_excluded_page_is_still_a_valid_link_target(tmp_path: Path):
    site = tmp_path / "site"
    page(site, "index.html", '<a href="print_page/#intro">go</a>')
    page(site, "print_page/index.html", '<h2 id="intro">Intro</h2>')
    assert run(str(site), "--exclude", "print_page/*") == 0


def test_without_an_exclusion_nothing_is_skipped(tmp_path: Path, capsys):
    site = tmp_path / "site"
    page(site, "index.html", '<h2 id="a">A</h2><a href="#a">self</a>')
    page(site, "print_page/index.html", '<h2 id="b">B</h2><a href="#b">self</a>')
    assert run(str(site)) == 0
    assert "Checked 2 anchor links" in capsys.readouterr().out


def test_base_is_read_from_site_url_so_absolute_links_are_checked(
    docs_repo: DocsRepo, capsys
):
    """A wrong base silently skips root-absolute links instead of failing."""
    docs_repo.write(
        "mkdocs.yml",
        "site_name: Test\nsite_url: https://example.invalid/halpi2/\n",
    )
    site = docs_repo.root / "site"
    page(site, "index.html", '<a href="/halpi2/guide/#nope">go</a>')
    page(site, "guide/index.html", '<h2 id="setup">Setup</h2>')
    assert run(str(site)) == 1
    assert "Checked 1 anchor links" in capsys.readouterr().out


def test_explicit_base_overrides_the_configured_one(docs_repo: DocsRepo, capsys):
    docs_repo.write(
        "mkdocs.yml",
        "site_name: Test\nsite_url: https://example.invalid/halpi2/\n",
    )
    site = docs_repo.root / "site"
    page(site, "index.html", '<a href="/other/guide/#nope">go</a>')
    page(site, "guide/index.html", '<h2 id="setup">Setup</h2>')
    assert run(str(site), "--base", "/other/") == 1


def test_root_absolute_link_outside_the_base_is_not_ours(tmp_path: Path, capsys):
    site = tmp_path / "site"
    page(site, "index.html", '<a href="/elsewhere/#x">go</a>')
    assert run(str(site), "--base", "/halpi2/") == 0


def test_excluding_every_page_is_not_a_pass(tmp_path: Path, capsys):
    """fnmatch crosses '/', so a broad pattern can silence the whole site."""
    site = tmp_path / "site"
    page(site, "index.html", '<a href="ghost/#x">go</a>')
    page(site, "sub/deep.html", '<a href="ghost/#y">go</a>')
    assert run(str(site)) == 1
    assert run(str(site), "--exclude", "*") == 2
    assert "every built page is excluded" in capsys.readouterr().err
    assert run(str(site), "--exclude", "*.html") == 2
