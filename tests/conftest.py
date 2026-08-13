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
