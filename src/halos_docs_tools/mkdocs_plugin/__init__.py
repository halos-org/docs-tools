"""The `halos-i18n` MkDocs plugin.

The subpackage is named `mkdocs_plugin` rather than `mkdocs` so that no import
inside this package is ambiguous about whether it means MkDocs itself.
"""

from halos_docs_tools.mkdocs_plugin.plugin import HalosI18nPlugin

__all__ = ["HalosI18nPlugin"]
