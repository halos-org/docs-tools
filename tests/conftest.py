"""A miniature documentation repository the checkers can be run against.

The staleness check reads real git blob hashes, so the fixture builds a real
git repository rather than mocking `git`. Mocking it would test the mock: the
whole mechanism is that `git hash-object` of the English page and the hash
recorded in the translation either match or do not.
"""

from __future__ import annotations

import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

MKDOCS = """\
site_name: Test docs
theme:
  name: material
markdown_extensions:
  - pymdownx.emoji:
      emoji_generator: !!python/name:material.extensions.emoji.to_svg
plugins:
  - search
  - i18n:
      docs_structure: folder
      languages:
        - locale: en
          name: English
          default: true
          build: true
        - locale: fi
          name: Suomi
          build: true
        - locale: sv
          name: Svenska
          build: true
"""

MKDOCS_NO_I18N = """\
site_name: Test docs
theme:
  name: material
plugins:
  - search
"""

MKDOCS_ONLY_DEFAULT = """\
site_name: Test docs
plugins:
  - i18n:
      docs_structure: folder
      languages:
        - locale: en
          name: English
          default: true
          build: true
"""


@dataclass
class DocsRepo:
    """A documentation repository under a temporary directory."""

    root: Path

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    def write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")
        return path

    def source(self, page: str, text: str = "# Title\n\nEnglish body.\n") -> Path:
        return self.write(f"docs/en/{page}", text)

    def blob(self, page: str) -> str:
        """The hash a translation of this English page should record."""
        return self.git("hash-object", f"docs/en/{page}")

    def translation(
        self,
        language: str,
        page: str,
        text: str = "# Otsikko\n\nKäännetty teksti.\n",
        stamp: str | None = "current",
    ) -> Path:
        """Write a translation. stamp: "current", None, or a literal hash."""
        if stamp == "current":
            stamp = self.blob(page)
        front = f"---\ntranslated_from: {stamp}\n---\n\n" if stamp else ""
        return self.write(f"docs/{language}/{page}", front + text)

    def commit(self, message: str = "docs: update") -> str:
        self.git("add", "-A")
        self.git("commit", "-m", message)
        return self.git("rev-parse", "HEAD")


@pytest.fixture
def docs_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DocsRepo:
    """An initialised repo with one English page, current in both locales.

    The checkers read `docs/` and `mkdocs.yml` relative to the working
    directory, so the fixture chdirs into the repository.
    """
    repo = DocsRepo(tmp_path)
    repo.git("init", "-q", "-b", "main")
    repo.git("config", "user.email", "test@example.invalid")
    repo.git("config", "user.name", "Test")

    repo.write("mkdocs.yml", MKDOCS)
    repo.source("index.md")
    monkeypatch.chdir(tmp_path)
    repo.translation("fi", "index.md")
    repo.translation("sv", "index.md")
    return repo


# A real site build is the only thing that proves the plugin. It has to run the
# i18n plugin's nested builds, Material's templates and MkDocs' own 404 page,
# and none of those can be faked usefully.

LOCALE_NAMES = {
    "en": "English",
    "fi": "Suomi",
    "fr": "Français",
    "de": "Deutsch",
    "sv": "Svenska",
    "es": "Español",
    "it": "Italiano",
    "nl": "Nederlands",
    "nb": "Norsk bokmål",
    "da": "Dansk",
}

TEN_LOCALES = list(LOCALE_NAMES)


@dataclass
class SiteRepo:
    """A buildable MkDocs site with one page per locale."""

    root: Path
    locales: list[str]

    def configure(
        self,
        *,
        site_url: str | None = "https://docs.example.invalid/product",
        plugin: bool | dict = True,
        custom_dir: str | None = None,
        pages: tuple[str, ...] = ("index.md", "guide/setup.md"),
    ) -> None:
        lines = ["site_name: Test docs"]
        if site_url is not None:
            lines.append(f"site_url: {site_url}")
        lines += ["theme:", "  name: material"]
        if custom_dir is not None:
            lines.append(f"  custom_dir: {custom_dir}")
        lines += ["plugins:", "  - search", "  - i18n:", "      docs_structure: folder"]
        lines.append("      languages:")
        for locale in self.locales:
            lines.append(f"        - locale: {locale}")
            lines.append(f"          name: {LOCALE_NAMES[locale]}")
            if locale == self.locales[0]:
                lines.append("          default: true")
            lines.append("          build: true")
        if plugin is True:
            lines.append("  - halos-i18n")
        elif isinstance(plugin, dict):
            lines.append("  - halos-i18n:")
            lines.append(_indent_yaml(plugin, 6))
        (self.root / "mkdocs.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")

        for locale in self.locales:
            for page in pages:
                stem = page.rsplit("/", 1)[-1].removesuffix(".md")
                self.write(
                    f"docs/{locale}/{page}",
                    f"# {stem} {locale}\n\n## Section {locale}\n\nBody for {locale}.\n",
                )

    def write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def build(self, *, strict: bool = True) -> Path:
        """Build the site and return its directory."""
        from mkdocs.commands.build import build as mkdocs_build
        from mkdocs.config import load_config

        config = load_config(str(self.root / "mkdocs.yml"), strict=strict)
        mkdocs_build(config)
        return self.root / "site"

    def page(self, relative: str) -> str:
        return (self.root / "site" / relative).read_text(encoding="utf-8")


def _indent_yaml(mapping: dict, spaces: int) -> str:
    import yaml

    body = yaml.safe_dump(mapping, allow_unicode=True, sort_keys=False)
    pad = " " * spaces
    return "\n".join(pad + line for line in body.rstrip().splitlines())


@pytest.fixture
def site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SiteRepo:
    """A ten-locale site, matching halpi2, halmet and sh-rpi."""
    monkeypatch.chdir(tmp_path)
    repo = SiteRepo(tmp_path, TEN_LOCALES)
    repo.configure()
    return repo


@pytest.fixture
def two_locale_site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SiteRepo:
    """A two-locale site, matching sh-esp32."""
    monkeypatch.chdir(tmp_path)
    repo = SiteRepo(tmp_path, ["en", "fi"])
    repo.configure()
    return repo
