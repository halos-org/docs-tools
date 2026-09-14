"""Make a multi-edition documentation site behave like one site.

`mkdocs-static-i18n` builds one edition per locale and leaves the rest to the
theme. Three things are then missing, and all three are the same concern:

- A visitor of the default edition is not sent to the edition matching their
  browser languages. GitHub Pages cannot negotiate content, so that choice has
  to happen in the browser.
- One `404.html` is served for every URL that does not resolve, in every
  edition, and the build can only produce one copy of it.
- The search index is merged across editions, so a search from a translated
  page returns hits in every other language.

They share the locale list, the edition roots and the Norwegian alias table, so
they are one plugin rather than three.
"""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from mkdocs.config import config_options
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin, event_priority
from mkdocs.utils import get_theme_dir

from halos_docs_tools.mkdocs_plugin.not_found import NOT_FOUND, WORDING

TEMPLATES = Path(__file__).parent / "templates"

# Rendered by MkDocs itself rather than from a page, so it carries no redirect
# script. `404.html` selects a language for it at runtime instead.
UNPAGED = "404.html"

ALTERNATES_MAP = re.compile(r"var ALTERNATES = (\{.*?\n    \});", re.S)
EDITION_LOCALES = re.compile(r'\n      "([a-z-]+)": \{\n        url:')
X_DEFAULT_LINK = re.compile(r'<link rel="alternate" [^>]*hreflang="x-default">')
HTML_LANG = re.compile(r'<html[^>]*\blang="([^"]*)"')
CONFIG_SCRIPT = re.compile(
    r'(<script id="__config" type="application/json">)(.*?)(</script>)', re.S
)


class HalosI18nConfig(config_options.Config):
    not_found = config_options.Type(dict, default={})


class HalosI18nPlugin(BasePlugin[HalosI18nConfig]):
    """Language selection, a multi-edition 404 page, and per-edition search."""

    def __init__(self):
        super().__init__()
        self._default_edition_404 = None

    @event_priority(-100)
    def on_config(self, config):
        """Publish what the templates need, and let Jinja find them.

        Priority -100 puts this after the i18n plugin has validated its own
        config, which is where the language list becomes trustworthy.
        """
        languages = _languages(config)

        default = [language.locale for language in languages if language.default]
        if len(default) != 1:
            raise PluginError(f"halos-i18n: expected one default locale, got {default}")
        locales = [language.locale for language in languages if language.build]

        config["extra"]["default_locale"] = default[0]
        config["extra"]["locales"] = locales
        config["extra"]["edition_roots"] = _edition_roots(config, locales, default[0])
        config["extra"]["not_found"] = _wording(self.config["not_found"], locales)
        config["extra"]["language_storage_key"] = _storage_key(config)

        _add_templates(config["theme"])
        return config

    def on_post_template(self, output, template_name, config):
        """Keep the default edition's 404 page instead of the last locale built.

        `mkdocs-static-i18n` builds the default language in the outer build,
        then loops over the remaining locales with nested `build()` calls. Every
        one of those writes `site/404.html`, so the file that survives belongs
        to whichever locale is last in `mkdocs.yml` — with that locale's chrome
        and a logo linking into that locale's edition. GitHub Pages serves that
        one file for every URL that does not resolve, in every edition.

        Replacing the output as it is rendered leaves nothing to undo
        afterwards. The template then picks the reader's language at runtime,
        which is what makes one stable page enough for ten editions.
        """
        if template_name != UNPAGED:
            return output
        if not _building(config):
            self._default_edition_404 = output
            return output
        return self._default_edition_404 or output

    @event_priority(-200)
    def on_post_build(self, config):
        """Check what the templates produced, after every edition is built.

        Priority -200 runs after the i18n plugin's nested builds, which it
        starts from its own post-build handler at -100.

        Every assumption these templates rest on degrades to omitted output
        rather than a build error: a plugin upgrade could ship a site that
        silently stops selecting a language. This is what makes that loud.

        The search index is split here too, before the checks, so that the
        checks read the pages as they ship.
        """
        if _building(config):
            return

        if len(config["extra"]["locales"]) < 2:
            return

        site_dir = Path(config["site_dir"])
        _split_search_index(config, site_dir)
        check_site(config, site_dir)


def check_site(config, site_dir):
    """Assert every built page still carries what the templates promised."""
    expected = sorted(locale.lower() for locale in config["extra"]["locales"])
    default = config["extra"]["default_locale"].lower()
    for page in sorted(Path(site_dir).rglob("*.html")):
        if page.name == UNPAGED and page.parent == Path(site_dir):
            _check_unpaged(page, expected, default)
        else:
            _check_page(page, expected)


def _split_search_index(config, site_dir):
    """Give every language edition its own search index.

    `mkdocs-static-i18n` merges all editions into one `search/search_index.json`,
    and Material resolves that file against `__config.base`, which points at the
    site root on every page. Searching from a translated page therefore returns
    hits in every other language.

    This splits the merged index by locale, writes each edition its own copy,
    and repoints `__config.base` on the edition's pages at the edition root,
    which is the only value Material derives the index URL from.
    """
    if not any(name.endswith("search") for name in config["plugins"]):
        return

    index_path = site_dir / "search" / "search_index.json"
    if not index_path.exists():
        raise PluginError(f"halos-i18n: no merged search index at {index_path}")

    default = config["extra"]["default_locale"]
    locales = [locale for locale in config["extra"]["locales"] if locale != default]

    index = json.loads(index_path.read_text(encoding="utf-8"))
    editions = {locale: [] for locale in locales}
    default_docs = []
    for doc in index["docs"]:
        locale, _, path = doc["location"].partition("/")
        if locale in editions:
            editions[locale].append({**doc, "location": path})
        else:
            default_docs.append(doc)

    empty = sorted(locale for locale, docs in editions.items() if not docs)
    if empty or not default_docs:
        raise PluginError(
            "halos-i18n: no index entries for "
            + ", ".join(empty + ([default] if not default_docs else []))
        )

    stemmers = set(index.get("config", {}).get("lang", []))
    for locale, docs in editions.items():
        edition_index = {
            **index,
            "docs": docs,
            "config": {
                **index["config"],
                "lang": [locale] if locale in stemmers else ["en"],
            },
        }
        target = site_dir / locale / "search" / "search_index.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(edition_index), encoding="utf-8")
        _repoint_base(site_dir / locale)

    index["docs"] = default_docs
    index["config"] = {
        **index["config"],
        "lang": [default] if default in stemmers else ["en"],
    }
    index_path.write_text(json.dumps(index), encoding="utf-8")


def _repoint_base(edition_dir):
    """Point `__config.base` at the edition root instead of the site root."""
    for page in edition_dir.rglob("*.html"):
        depth = len(page.parent.relative_to(edition_dir).parts)
        base = "/".join([".."] * depth) if depth else "."
        page.write_text(_rebased(page, base), encoding="utf-8")


def _rebased(page, base):
    def rewrite(match):
        settings = json.loads(match.group(2))
        settings["base"] = base
        return match.group(1) + json.dumps(settings) + match.group(3)

    text = page.read_text(encoding="utf-8")
    patched, count = CONFIG_SCRIPT.subn(rewrite, text, count=1)
    if not count:
        raise PluginError(f"halos-i18n: no __config script in {page}")
    return patched


def _building(config):
    """True inside one of the i18n plugin's nested per-locale builds."""
    i18n = config["plugins"].get("i18n")
    return i18n is not None and i18n.building


def _check_page(page, expected):
    text = page.read_text(encoding="utf-8")

    lang = HTML_LANG.search(text)
    if lang is None or lang.group(1).lower() not in expected:
        found = lang.group(1) if lang else "nothing"
        raise PluginError(f"halos-i18n: {page} declares lang={found}")

    if len(X_DEFAULT_LINK.findall(text)) != 1:
        raise PluginError(f"halos-i18n: no single x-default link in {page}")

    match = ALTERNATES_MAP.search(text)
    if match is None:
        raise PluginError(f"halos-i18n: no language script in {page}")
    locales = sorted(json.loads(match.group(1)))
    if locales != expected:
        raise PluginError(f"halos-i18n: {page} offers {locales}, expected {expected}")

    if '<a href="' not in text or "md-select__link" not in text:
        raise PluginError(f"halos-i18n: no language selector in {page}")


def _check_unpaged(page, expected, default_locale):
    """The 404 page ships every edition's wording and picks one in the browser."""
    text = page.read_text(encoding="utf-8")

    lang = HTML_LANG.search(text)
    if lang is None or lang.group(1).lower() != default_locale:
        found = lang.group(1) if lang else "nothing"
        raise PluginError(
            f"halos-i18n: {page} was built as {found}, not {default_locale}"
        )

    locales = sorted(EDITION_LOCALES.findall(text))
    if locales != expected:
        raise PluginError(f"halos-i18n: {page} offers {locales}, expected {expected}")


def _add_templates(theme):
    """Put the package templates behind the site's own and ahead of the theme.

    Anything the site supplies through `custom_dir` keeps the last word, so a
    repository that needs its own template reintroduces it and wins with no
    change here. Anchoring on the theme directory rather than on a `custom_dir`
    that may not be set also keeps a parent theme behind us.
    """
    anchor = get_theme_dir(theme.name) if theme.name else None
    at = theme.dirs.index(anchor) if anchor in theme.dirs else 0
    theme.dirs.insert(at, str(TEMPLATES))


def _languages(config):
    i18n = config["plugins"].get("i18n")
    if i18n is None:
        raise PluginError("halos-i18n: the i18n plugin is not enabled")
    return i18n.config.languages


def _edition_roots(config, locales, default):
    """Where each edition starts, as a root-absolute path.

    `404.html` is served for URLs at any depth, so its links cannot be
    relative, and MkDocs' `url` filter has no spelling for the site root on
    that page. Build the roots from `site_url` instead.
    """
    base = urlsplit(config["site_url"] or "/").path
    if not base.endswith("/"):
        base += "/"
    return {
        locale: base if locale == default else f"{base}{locale}/" for locale in locales
    }


def _wording(override, locales):
    """Package defaults, with a repository's override replacing a whole locale.

    Replacing rather than merging keeps a half-translated locale impossible:
    an override either supplies all three strings or supplies none.
    """
    wording = {**NOT_FOUND, **override}
    missing = [
        locale
        for locale in locales
        if sorted(wording.get(locale) or {}) != sorted(WORDING)
    ]
    if missing:
        raise PluginError(f"halos-i18n: not_found needs {list(WORDING)} for {missing}")
    return wording


def _storage_key(config):
    """A local-storage key distinct per site.

    The sites share an origin, so they share local storage. A shared key would
    let one site's language choice follow a reader into another.
    """
    path = urlsplit(config["site_url"] or "/").path.strip("/")
    return f"halos-docs.{path.replace('/', '.') or 'root'}.language"
