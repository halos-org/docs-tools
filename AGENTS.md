# halos-docs-tools - Agent Context

**Document Purpose**: Context for AI assistants working in this repository.

## What this is

Six documentation checkers, packaged so that a MkDocs documentation repository
can pin them and get the identical code in CI and on a developer's machine. The
checkers were extracted from `hatlabs/halpi2`, where they lived as `scripts/`.

Consumers:

- `hatlabs/halpi2` — nine locales, full translation gate
- `halos-org/docs.halos.fi` — no translations, anchor validation only

## The six commands

Console entry points are declared in `pyproject.toml` under `[project.scripts]`.
**They are a public interface.** A second repository pins them, and the
`translate-page` skill in `hatlabs/halpi2` calls them by name. Renaming one is a
breaking change for every consumer.

Each module lives at `src/halos_docs_tools/<name>.py` and exposes `main()`.

## Conventions

- Commands run from the root of a documentation repository. They read `docs/`
  and `mkdocs.yml` relative to the working directory. Do not add hidden defaults
  that make them work from elsewhere without saying so.
- Glossaries and language rules are repository content, not package content.
  Where a checker needs them, the path is a CLI option with a default.
- The translation stamp format — `translated_from` in frontmatter, holding a git
  blob hash — is fixed. Consumers have thousands of pages carrying it.

## Distribution

This repository produces no `.deb`. There is no `VERSION` file, no
`debian/changelog`, and no APT dispatch — the workspace version-bump policy
governs `.deb`-producing repositories and does not apply here.

Releases are `pyproject.toml` version plus a `vX.Y.Z` git tag. Consumers pin the
tag.

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
