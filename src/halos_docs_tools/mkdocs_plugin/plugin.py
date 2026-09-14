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

from mkdocs.plugins import BasePlugin

TEMPLATES = Path(__file__).parent / "templates"


class HalosI18nPlugin(BasePlugin):
    """Language selection, a multi-edition 404 page, and per-edition search."""
