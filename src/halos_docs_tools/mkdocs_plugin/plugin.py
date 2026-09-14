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

from pathlib import Path
from urllib.parse import urlsplit

from mkdocs.config import config_options
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin, event_priority
from mkdocs.utils import get_theme_dir

from halos_docs_tools.mkdocs_plugin.not_found import NOT_FOUND, WORDING

TEMPLATES = Path(__file__).parent / "templates"


class HalosI18nConfig(config_options.Config):
    not_found = config_options.Type(dict, default={})


class HalosI18nPlugin(BasePlugin[HalosI18nConfig]):
    """Language selection, a multi-edition 404 page, and per-edition search."""

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
