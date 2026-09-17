"""What a built site actually carries.

The templates are only provable against a real build: the i18n plugin's nested
builds, Material's chrome and MkDocs' own 404 page all have to run.
"""

import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from conftest import SiteRepo

ALTERNATES_MAP = re.compile(r"var ALTERNATES = (\{.*?\n    \});", re.S)
EDITIONS_MAP = re.compile(r'\n      "([a-z-]+)": \{\n        url:')
X_DEFAULT = re.compile(r'<link rel="alternate" [^>]*hreflang="x-default">')
STORAGE_KEY = re.compile(r'var STORAGE_KEY = "([^"]+)"')


def alternates(html: str) -> dict:
    return json.loads(ALTERNATES_MAP.search(html).group(1))


def test_the_wheel_carries_the_templates(tmp_path: Path):
    """An editable install hides a missing package-data entry.

    Only a built wheel proves a consumer installing from a tag gets the
    templates, so this builds one.
    """
    uv = shutil.which("uv")
    assert uv, "uv builds this package; see ./run"
    root = Path(__file__).resolve().parent.parent
    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=root,
        check=True,
        capture_output=True,
    )
    (wheel,) = tmp_path.glob("*.whl")
    shipped = {
        name
        for name in zipfile.ZipFile(wheel).namelist()
        if name.startswith("halos_docs_tools/mkdocs_plugin/templates/")
    }
    assert shipped == {
        "halos_docs_tools/mkdocs_plugin/templates/main.html",
        "halos_docs_tools/mkdocs_plugin/templates/404.html",
    }


def test_every_built_locale_is_offered_on_a_default_edition_page(site: SiteRepo):
    site.build()
    assert sorted(alternates(site.page("index.html"))) == sorted(site.locales)


def test_a_default_edition_page_carries_one_x_default_link(site: SiteRepo):
    site.build()
    assert len(X_DEFAULT.findall(site.page("index.html"))) == 1


def test_a_translated_page_declares_its_own_language(site: SiteRepo):
    site.build()
    html = site.page("fi/index.html")
    assert 'lang="fi"' in html
    assert "md-select__link" in html


def test_the_announce_nav_is_on_every_edition(site: SiteRepo):
    site.build()
    for relative in ("index.html", "fi/index.html", "da/guide/setup/index.html"):
        assert 'class="hat-labs-nav"' in site.page(relative)


def test_the_404_page_ships_every_edition(site: SiteRepo):
    site.build()
    assert sorted(EDITIONS_MAP.findall(site.page("404.html"))) == sorted(site.locales)


def test_the_404_page_renders_the_default_wording_without_scripting(site: SiteRepo):
    """A reader with scripting disabled still gets a usable page."""
    site.build()
    html = site.page("404.html")
    assert "<title>Page not found</title>" in html
    assert 'data-404="message"' in html
    assert "The page you asked for does not exist." in html


def test_two_locales_offer_two_editions(two_locale_site: SiteRepo):
    two_locale_site.build()
    assert sorted(alternates(two_locale_site.page("index.html"))) == ["en", "fi"]
    assert sorted(EDITIONS_MAP.findall(two_locale_site.page("404.html"))) == [
        "en",
        "fi",
    ]


def test_the_storage_key_follows_the_site_url(site: SiteRepo):
    site.configure(site_url="https://docs.example.invalid/halmet")
    site.build()
    assert STORAGE_KEY.search(site.page("index.html")).group(1) == (
        "halos-docs.halmet.language"
    )
