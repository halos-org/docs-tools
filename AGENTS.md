# halos-docs-tools - Agent Context

**Document Purpose**: Context for AI assistants working in this repository.

## What this is

Six documentation checkers and one MkDocs plugin, packaged so that a MkDocs
documentation repository can pin them and get the identical code in CI and on a
developer's machine. The checkers were extracted from `hatlabs/halpi2`, where
they lived as `scripts/`. The `halos-i18n` plugin was extracted from the same
repository, where it lived as two files under `hooks/` and two theme templates
under `docs/overrides/`.

Consumers, all pinning a tag:

- `hatlabs/halpi2`, `hatlabs/halmet`, `hatlabs/sh-rpi` — English plus nine
  translations each, full translation gate through `halos-org/shared-workflows`
- `hatlabs/sh-esp32` — English plus Finnish, same gate
- `halos-org/docs` (docs.halos.fi) — no translations, `check-anchors` only,
  called directly from its own build job

`halos-org/shared-workflows` calls the CLI by name and by flag, so it is a
consumer too even though it installs nothing: see `translation-status.yml`.

## The six commands and the plugin

Console entry points are declared in `pyproject.toml` under `[project.scripts]`.
**They are a public interface.** A second repository pins them, and the
`translate-page` skill in `hatlabs/halpi2` calls them by name. Renaming one is a
breaking change for every consumer.

Each module lives at `src/halos_docs_tools/<name>.py` and exposes `main()`.

The plugin is declared under the `mkdocs.plugins` entry-point group as
`halos-i18n`. **That name is a public interface for the same reason.** Four
repositories name it in `mkdocs.yml`, and a plugin MkDocs cannot find is a build
error in someone else's repository. `tests/test_plugin_entry_point.py` is what
makes a rename deliberate.

The plugin lives at `src/halos_docs_tools/mkdocs_plugin/`, with its two theme
templates under `templates/`. The subpackage is not named `mkdocs`, so that no
import is ambiguous about whether it means MkDocs itself. The templates are
shipped through `[tool.setuptools.package-data]`; an editable install resolves
them from the source tree, so only the wheel test proves the packaging.

## Conventions

- Commands run from the root of a documentation repository. They read `docs/`
  and `mkdocs.yml` relative to the working directory. Do not add hidden defaults
  that make them work from elsewhere without saying so.
- The plugin inserts its template directory immediately ahead of the theme's
  own, never at a fixed index. `mkdocs-static-i18n` puts its sitemap template at
  the front, and anything a repository sets as `custom_dir` has to keep the last
  word.
- Glossaries and language rules are repository content, not package content.
  Where a checker needs them, the path is a CLI option with a default.
- The translation stamp format — `translated_from` in frontmatter, holding a git
  blob hash — is fixed. Consumers have thousands of pages carrying it.
- `translation-status --check` fails on `missing`, `unstamped` and `orphaned`
  wherever they came from, and on `stale` only for pages changed since
  `--since REF` when that is given. The split is deliberate: the first three are
  structural, while gating every stale page in the repository makes an
  English-only edit unmergeable until all its translations land in the same
  change. Do not quietly widen either half.

## Distribution

Releases go through the shared workflows in `halos-org/shared-workflows` with
`build-deb: false`: no `.deb`, no `debian/changelog`, no APT dispatch, and
nothing published to a registry. `.github/scripts/generate-release-notes.sh`
replaces the shared APT install notes with the git pin.

- `pr.yml` runs `pr-checks.yml`. The repo-local actions under
  `.github/actions/` supply the tests (`run-tests`) and the check that `VERSION`
  matches `pyproject.toml` (`check-versions`).
- `main.yml` runs `build-release.yml` on every merge. It creates a
  `vX.Y.Z+N_pre` pre-release and a draft `vX.Y.Z+N` release.
- Publishing the draft makes `vX.Y.Z+N` a stable release. Consumers pin that
  tag.

The workspace version-bump policy applies: bump once per release cycle with
`./run bumpversion patch|minor|major`, which updates `VERSION` and
`pyproject.toml` together. Never tag by hand.

## Development

```
./run deps      install dependencies
./run test      run the test suite
./run lint      check with ruff
./run check     lint and test, as CI does
```

Install the pre-commit hooks after cloning with `./run install-hooks`.

## Testing

Tests build a miniature documentation tree in a throwaway git repository —
`tests/conftest.py` — because the staleness check reads real git blob hashes.
Reuse those fixtures rather than mocking `git`.
