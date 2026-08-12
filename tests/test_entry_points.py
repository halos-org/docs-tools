"""The six command names are a public interface.

A consumer repository pins them in CI, and the translate-page skill in
hatlabs/halpi2 calls them by name. Renaming one breaks both, silently, at a
distance. This test is the thing that makes that a deliberate act.
"""

from importlib.metadata import entry_points

COMMANDS = {
    "translation-status": "halos_docs_tools.translation_status:main",
    "stamp-translation": "halos_docs_tools.stamp_translation:main",
    "map-anchors": "halos_docs_tools.map_anchors:main",
    "check-glossary": "halos_docs_tools.check_glossary:main",
    "check-typography": "halos_docs_tools.check_typography:main",
    "check-anchors": "halos_docs_tools.check_anchors:main",
}


def declared() -> dict[str, str]:
    return {
        e.name: e.value
        for e in entry_points(group="console_scripts")
        if e.module.startswith("halos_docs_tools")
    }


def test_all_six_commands_are_declared():
    assert declared() == COMMANDS
