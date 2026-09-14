"""The checks that make a silent regression loud.

Everything the templates depend on — `config.extra.alternate`, the i18n
plugin's nested builds, Material's language selector — degrades to omitted
output rather than an error. A dependency upgrade could therefore ship a site
that quietly stops selecting a language. These tests exist to prove the checks
fail when that happens, which a passing build never does.
"""

import re

import pytest
from conftest import LOCALE_NAMES, SiteRepo
from mkdocs.exceptions import Abort, PluginError

from halos_docs_tools.mkdocs_plugin import plugin


def test_a_ten_locale_site_builds_clean(site: SiteRepo):
    site.build()
    assert (site.root / "site" / "404.html").exists()


def test_the_surviving_404_belongs_to_the_default_edition(site: SiteRepo):
    """Danish is last in the configuration, as it is in every real site.

    Without the render-time replacement this page would carry Danish chrome and
    a logo linking into the Danish edition, for every URL that does not resolve
    in any edition.
    """
    assert site.locales[-1] == "da"
    site.build()
    html = site.page("404.html")
    assert 'lang="en"' in html
    assert "<title>Page not found</title>" in html
    assert "Siden blev ikke fundet" in html  # shipped as data, not as chrome


def test_a_two_locale_site_is_still_checked(two_locale_site: SiteRepo):
    two_locale_site.build()
    assert sorted(plugin.EDITION_LOCALES.findall(two_locale_site.page("404.html"))) == [
        "en",
        "fi",
    ]


def test_a_single_locale_site_skips_the_checks(tmp_path, monkeypatch):
    """One edition has no other edition to offer, so there is nothing to check."""
    monkeypatch.chdir(tmp_path)
    site = SiteRepo(tmp_path, ["en"])
    site.configure()
    site.build()
    assert (tmp_path / "site" / "index.html").exists()


def test_a_page_that_lost_its_x_default_link_fails_the_build(
    site: SiteRepo, monkeypatch, caplog
):
    """MkDocs turns a PluginError into an abort, so this is what CI sees."""
    monkeypatch.setattr(plugin, "X_DEFAULT_LINK", re.compile("never-present"))
    with pytest.raises(Abort):
        site.build()
    assert "no single x-default link" in caplog.text


def test_a_page_that_lost_the_language_script_fails_the_build(
    site: SiteRepo, monkeypatch, caplog
):
    monkeypatch.setattr(plugin, "ALTERNATES_MAP", re.compile("(never-present)"))
    with pytest.raises(Abort):
        site.build()
    assert "no language script" in caplog.text


def test_a_built_locale_missing_from_the_map_fails(site: SiteRepo):
    """A locale that builds but is never offered is the regression to catch."""
    site.build()
    page = site.root / "site" / "index.html"
    page.write_text(page.read_text().replace('"da": ', '"zz": '), encoding="utf-8")
    config = _configured(site)
    with pytest.raises(PluginError, match=r"offers.*expected"):
        config["plugins"]["halos-i18n"].on_post_build(config)


def test_a_page_declaring_an_unbuilt_language_fails(site: SiteRepo):
    site.build()
    page = site.root / "site" / "fi" / "index.html"
    page.write_text(
        page.read_text().replace('lang="fi"', 'lang="zz"'), encoding="utf-8"
    )
    config = _configured(site)
    with pytest.raises(PluginError, match="declares lang=zz"):
        config["plugins"]["halos-i18n"].on_post_build(config)


def test_a_404_built_as_the_wrong_edition_fails(site: SiteRepo):
    site.build()
    page = site.root / "site" / "404.html"
    page.write_text(
        page.read_text().replace('lang="en"', 'lang="da"', 1), encoding="utf-8"
    )
    config = _configured(site)
    with pytest.raises(PluginError, match="was built as da, not en"):
        config["plugins"]["halos-i18n"].on_post_build(config)


def test_a_404_offering_the_wrong_editions_fails(site: SiteRepo):
    site.build()
    page = site.root / "site" / "404.html"
    page.write_text(
        page.read_text().replace('"da": {\n        url:', '"zz": {\n        url:'),
        encoding="utf-8",
    )
    config = _configured(site)
    with pytest.raises(PluginError, match=r"404.html offers.*expected"):
        config["plugins"]["halos-i18n"].on_post_build(config)


def test_a_page_without_a_language_selector_fails(site: SiteRepo):
    site.build()
    page = site.root / "site" / "index.html"
    page.write_text(
        page.read_text().replace("md-select__link", "md-gone"), encoding="utf-8"
    )
    config = _configured(site)
    with pytest.raises(PluginError, match="no language selector"):
        config["plugins"]["halos-i18n"].on_post_build(config)


def _configured(site: SiteRepo):
    """The site's config with `on_config` fired, for checking a built site."""
    from mkdocs.config import load_config

    config = load_config(str(site.root / "mkdocs.yml"), strict=True)
    config["plugins"].on_config(config)
    assert set(config["extra"]["locales"]) == set(LOCALE_NAMES)
    return config
