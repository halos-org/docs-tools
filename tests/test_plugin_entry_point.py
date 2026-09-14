"""The plugin name is a public interface.

Four documentation repositories name `halos-i18n` in their `mkdocs.yml`.
Renaming it breaks all four, silently, at a distance — a MkDocs plugin that
cannot be found is a build error in someone else's repository, not here. This
test is what makes a rename a deliberate act, as `test_entry_points.py` does
for the six console commands.
"""

from importlib.metadata import entry_points

from conftest import SiteRepo

PLUGIN = "halos-i18n"
TARGET = "halos_docs_tools.mkdocs_plugin.plugin:HalosI18nPlugin"


def declared() -> dict[str, str]:
    return {
        e.name: e.value
        for e in entry_points(group="mkdocs.plugins")
        if e.module.startswith("halos_docs_tools")
    }


def test_the_plugin_is_declared_under_the_name_consumers_use():
    assert declared() == {PLUGIN: TARGET}


def test_the_declared_target_resolves_to_a_plugin_class():
    from mkdocs.plugins import BasePlugin

    (entry,) = (e for e in entry_points(group="mkdocs.plugins") if e.name == PLUGIN)
    assert issubclass(entry.load(), BasePlugin)


def test_the_templates_ship_with_the_installed_package():
    """A missing package-data entry leaves a wheel with no templates.

    Resolving the directory from the installed module rather than from the
    source tree is what makes this fail when the packaging is wrong.
    """
    from halos_docs_tools.mkdocs_plugin import plugin

    assert plugin.TEMPLATES.is_dir()


def test_a_site_naming_the_plugin_loads(site: SiteRepo):
    from mkdocs.config import load_config

    config = load_config(str(site.root / "mkdocs.yml"), strict=True)
    assert PLUGIN in config["plugins"]
