# halos-docs-tools

Documentation checkers for HaLOS and Hat Labs MkDocs sites: translation status,
stamping, anchor validation, glossary and typography checks.

The same code runs in CI and on a laptop. Every check a pull request must pass is
runnable before you push.

## Installing

Add it to a documentation repository's `pyproject.toml`, pinned to a tag:

```toml
dependencies = [
    "halos-docs-tools @ git+https://github.com/halos-org/docs-tools@v0.1.0",
]
```

`uv sync` then puts all six commands on the path. Each repository pins its own
version; upgrading is a deliberate edit to that pin.

## Commands

Run them from the root of a documentation repository — they expect `docs/` and
`mkdocs.yml` in the working directory.

| Command | Purpose |
|:---|:---|
| `translation-status` | report which translations are missing or out of date |
| `stamp-translation` | record the English source a translation was written against |
| `map-anchors` | rewrite English anchor fragments to the translated slugs |
| `check-glossary` | verify a translation uses the terms its glossary prescribes |
| `check-typography` | check quotation pairing and unit spacing per language |
| `check-anchors` | verify every internal anchor in a built site resolves |

Glossaries and per-language rules stay in the documentation repository. This
package brings the checkers, not the terminology.

### Generated pages and `check-anchors`

Some plugins generate a page whose internal fragments the checker cannot
resolve. `mkdocs-print-site-plugin` is one: on `docs.halos.fi` its single-page
export accounts for 690 broken fragments while the 36 content pages are clean.
Exclude such pages by path pattern:

```
check-anchors site --exclude 'print_page/*'
```

An excluded page contributes no links to the check. Its own headings stay
linkable, so other pages may still point into it.

`--base`, used to resolve root-absolute links, is read from `site_url` in
`mkdocs.yml`. A base that does not match the site makes the checker skip every
root-absolute link and report a pass it did not earn, so override it only when
you know the built site differs from the configuration.

## How translation staleness is detected

A translation records the git blob hash of the English page it was written
against, in its own frontmatter:

```yaml
---
translated_from: <blob hash of docs/en/<path> at translation time>
---
```

The English page carries nothing. Editing it changes its content, which changes
its hash, which makes every translation of it report as stale on its own.

`translation-status` classifies each page in each configured locale as `current`,
`stale`, `missing`, `unstamped` or `orphaned`.

### Failing a build on it

```
translation-status --check
```

exits non-zero when any page in any configured locale is anything but
`current`, and names every entry responsible. Without `--check` the command
only reports, whatever it finds.

The gate is a property of the repository, not of a pull request's diff, so
`--only-pages` narrows the report and never the rule.

One consequence is worth knowing before you meet it: adding a locale to
`mkdocs.yml` makes every page `missing` in that locale immediately. A new
locale therefore arrives in a single pull request, together with its pages.

## Development

```
./run deps      install dependencies
./run test      run the test suite
./run lint      check with ruff
./run check     lint and test, as CI does
```

## License

MIT. Copyright Hat Labs Oy.
