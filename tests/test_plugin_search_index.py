"""One search index per edition.

`mkdocs-static-i18n` merges every edition into one index, and Material resolves
it against `__config.base`, which points at the site root on every page. A
search from a Finnish page therefore returns hits in nine other languages.
"""

import json
import re

import pytest
from conftest import SiteRepo
from mkdocs.exceptions import PluginError

from halos_docs_tools.mkdocs_plugin import plugin

CONFIG_SCRIPT = re.compile(
    r'<script id="__config" type="application/json">(.*?)</script>', re.S
)


def index(site: SiteRepo, relative: str) -> dict:
    return json.loads((site.root / "site" / relative).read_text(encoding="utf-8"))


def base(site: SiteRepo, relative: str) -> str:
    html = site.page(relative)
    return json.loads(CONFIG_SCRIPT.search(html).group(1))["base"]


def test_every_translated_edition_gets_its_own_index(site: SiteRepo):
    site.build()
    for locale in site.locales[1:]:
        docs = index(site, f"{locale}/search/search_index.json")["docs"]
        bodies = [doc["text"] for doc in docs if doc["text"]]
        assert bodies, locale
        assert all(f"Body for {locale}." in text for text in bodies)


def test_the_root_index_keeps_only_the_default_edition(site: SiteRepo):
    site.build()
    docs = index(site, "search/search_index.json")["docs"]
    assert docs
    assert not any(doc["location"].startswith(("fi/", "da/")) for doc in docs)


def test_an_edition_index_drops_the_locale_from_each_location(site: SiteRepo):
    site.build()
    docs = index(site, "fi/search/search_index.json")["docs"]
    assert not any(doc["location"].startswith("fi/") for doc in docs)


def test_the_base_is_the_edition_root_at_every_depth(site: SiteRepo):
    site.build()
    assert base(site, "fi/index.html") == "."
    assert base(site, "fi/guide/setup/index.html") == "../.."


def test_the_default_edition_keeps_the_site_root_as_its_base(site: SiteRepo):
    site.build()
    assert base(site, "index.html") == "."


def test_a_locale_lunr_stems_keeps_its_own_stemmer(site: SiteRepo):
    site.build()
    assert index(site, "fi/search/search_index.json")["config"]["lang"] == ["fi"]


def test_a_locale_lunr_does_not_stem_falls_back_to_english(site: SiteRepo):
    """lunr has no `nb` stemmer — it spells Norwegian `no` — so `nb` gets `en`.

    Naming the locale rather than deriving it keeps the test honest: the merged
    index is rewritten by the split, so its stemmer list cannot be read back
    afterwards to work out what was available.
    """
    site.build()
    assert index(site, "nb/search/search_index.json")["config"]["lang"] == ["en"]
    assert index(site, "da/search/search_index.json")["config"]["lang"] == ["da"]


def test_two_locales_split_into_one_edition_index_plus_the_root(
    two_locale_site: SiteRepo,
):
    two_locale_site.build()
    site_dir = two_locale_site.root / "site"
    assert (site_dir / "fi" / "search" / "search_index.json").exists()
    assert (site_dir / "search" / "search_index.json").exists()


def test_a_missing_merged_index_is_refused(site: SiteRepo):
    site.build()
    (site.root / "site" / "search" / "search_index.json").unlink()
    with pytest.raises(PluginError, match="no merged search index"):
        plugin._split_search_index(_configured(site), site.root / "site")


def test_an_edition_with_no_entries_is_refused(two_locale_site: SiteRepo):
    """A locale that builds but indexes nothing would search the wrong edition.

    The merged index is written fresh here. The real build already split it, so
    reusing what is on disk would find every edition empty and say so about all
    of them rather than about the one this test removes.
    """
    two_locale_site.build()
    merged = two_locale_site.root / "site" / "search" / "search_index.json"
    merged.write_text(
        json.dumps(
            {
                "config": {"lang": ["en", "fi"]},
                "docs": [{"location": "index.html", "text": "English"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PluginError, match="no index entries for fi"):
        plugin._split_search_index(
            _configured(two_locale_site), two_locale_site.root / "site"
        )


def test_a_page_without_a_config_script_is_refused(site: SiteRepo):
    site.build()
    page = site.root / "site" / "fi" / "index.html"
    page.write_text(CONFIG_SCRIPT.sub("", page.read_text()), encoding="utf-8")
    with pytest.raises(PluginError, match="no __config script"):
        plugin._repoint_base(site.root / "site" / "fi")


def test_a_site_without_a_search_plugin_is_left_alone(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    site = SiteRepo(tmp_path, ["en", "fi"])
    site.configure()
    config = (tmp_path / "mkdocs.yml").read_text().replace("  - search\n", "")
    (tmp_path / "mkdocs.yml").write_text(config)
    site.build()
    assert not (tmp_path / "site" / "search").exists()


def _configured(site: SiteRepo):
    from mkdocs.config import load_config

    config = load_config(str(site.root / "mkdocs.yml"), strict=True)
    config["plugins"].on_config(config)
    return config
