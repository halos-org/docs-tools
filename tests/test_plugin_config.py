"""What the plugin publishes for the templates, and where it puts them.

Every one of these facts degrades to omitted output rather than a build error
if it goes missing, which is why they are asserted here and again against the
built site in `test_plugin_post_build.py`.
"""

from pathlib import Path

import pytest
from conftest import SiteRepo
from mkdocs.config import load_config
from mkdocs.exceptions import PluginError


def configured(site: SiteRepo):
    """Load the config and fire `on_config`, which `load_config` does not.

    MkDocs dispatches plugin events from the build, so a test that only loads
    the config sees none of the plugin's work.
    """
    config = load_config(str(site.root / "mkdocs.yml"), strict=True)
    return config["plugins"].on_config(config) or config


def test_ten_locales_are_published_in_order(site: SiteRepo):
    extra = configured(site)["extra"]
    assert extra["default_locale"] == "en"
    assert extra["locales"] == [
        "en",
        "fi",
        "fr",
        "de",
        "sv",
        "es",
        "it",
        "nl",
        "nb",
        "da",
    ]


def test_edition_roots_put_the_default_at_the_base(site: SiteRepo):
    roots = configured(site)["extra"]["edition_roots"]
    assert roots["en"] == "/product/"
    assert roots["fi"] == "/product/fi/"


def test_two_locales_publish_two_edition_roots(two_locale_site: SiteRepo):
    roots = configured(two_locale_site)["extra"]["edition_roots"]
    assert roots == {"en": "/product/", "fi": "/product/fi/"}


def test_a_site_url_without_a_trailing_slash_still_yields_one(site: SiteRepo):
    site.configure(site_url="https://docs.example.invalid/product")
    assert configured(site)["extra"]["edition_roots"]["en"] == "/product/"


def test_an_unset_site_url_falls_back_to_the_root(site: SiteRepo):
    site.configure(site_url=None)
    roots = configured(site)["extra"]["edition_roots"]
    assert roots["en"] == "/"
    assert roots["fi"] == "/fi/"


def names(config) -> list[str]:
    return ["/".join(Path(d).parts[-2:]) for d in config["theme"].dirs]


def test_the_template_directory_goes_after_a_custom_dir(site: SiteRepo):
    """A repository that reintroduces `custom_dir` keeps the last word."""
    site.write("overrides/.keep", "")
    site.configure(custom_dir="overrides")
    order = names(configured(site))
    ours = order.index("mkdocs_plugin/templates")
    assert order[ours - 1].endswith("/overrides")
    assert order[ours + 1] == "material/templates"


def test_the_template_directory_goes_immediately_ahead_of_the_theme(site: SiteRepo):
    order = names(configured(site))
    assert order[order.index("mkdocs_plugin/templates") + 1] == "material/templates"


def test_the_i18n_sitemap_template_is_not_shadowed(site: SiteRepo):
    """`mkdocs-static-i18n` supplies its own sitemap template at the front.

    Inserting at a fixed index would have displaced it. Anchoring on the theme
    directory is what keeps it reachable.
    """
    order = names(configured(site))
    assert order.index("mkdocs_static_i18n/custom_i18n_sitemap") < order.index(
        "mkdocs_plugin/templates"
    )


def test_the_plugin_never_shadows_the_theme(site: SiteRepo):
    """Material's own templates must still be reachable behind ours."""
    dirs = [Path(d).parts[-2:] for d in configured(site)["theme"].dirs]
    assert ("material", "templates") in [tuple(p) for p in dirs]


def test_two_default_locales_are_refused(site: SiteRepo):
    text = (site.root / "mkdocs.yml").read_text()
    text = text.replace(
        "        - locale: fi\n          name: Suomi\n",
        "        - locale: fi\n          name: Suomi\n          default: true\n",
    )
    (site.root / "mkdocs.yml").write_text(text)
    with pytest.raises(PluginError, match=r"one default locale.*'en'.*'fi'"):
        configured(site)


def test_a_site_without_the_i18n_plugin_is_refused(site: SiteRepo):
    (site.root / "mkdocs.yml").write_text(
        "site_name: Test docs\nplugins:\n  - halos-i18n\n"
    )
    with pytest.raises(PluginError, match="i18n plugin is not enabled"):
        configured(site)


def test_wording_covers_every_locale_the_package_ships(site: SiteRepo):
    wording = configured(site)["extra"]["not_found"]
    for locale in configured(site)["extra"]["locales"]:
        assert sorted(wording[locale]) == ["home", "message", "title"]


def test_an_override_replaces_one_locale_and_leaves_the_rest(site: SiteRepo):
    mine = {"title": "Ei löydy", "message": "Ei ole.", "home": "Etusivulle"}
    site.configure(plugin={"not_found": {"fi": mine}})
    wording = configured(site)["extra"]["not_found"]
    assert wording["fi"] == mine
    assert wording["sv"]["title"] == "Sidan hittades inte"


def test_a_locale_with_no_wording_at_all_is_refused(site: SiteRepo):
    """A site building a locale the package never translated must say so."""
    site.locales = ["en", "fi", "xx"]
    text = (site.root / "mkdocs.yml").read_text()
    text = text.replace(
        "  - halos-i18n",
        "        - locale: xx\n          name: Test\n          build: true\n  - halos-i18n",
    )
    (site.root / "mkdocs.yml").write_text(text)
    with pytest.raises(PluginError, match=r"not_found needs.*'xx'"):
        configured(site)


def test_a_partial_override_is_refused(site: SiteRepo):
    site.configure(plugin={"not_found": {"fi": {"title": "Ei löydy"}}})
    with pytest.raises(PluginError, match=r"not_found needs.*'fi'"):
        configured(site)


def test_sites_at_different_paths_get_different_storage_keys(site: SiteRepo):
    site.configure(site_url="https://docs.example.invalid/halpi2")
    first = configured(site)["extra"]["language_storage_key"]
    site.configure(site_url="https://docs.example.invalid/halmet")
    second = configured(site)["extra"]["language_storage_key"]
    assert first != second
    assert first == "halos-docs.halpi2.language"


def test_a_site_at_the_origin_root_still_gets_a_key(site: SiteRepo):
    site.configure(site_url="https://docs.example.invalid/")
    assert configured(site)["extra"]["language_storage_key"].endswith(".language")
