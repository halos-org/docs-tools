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

## Development

```
./run deps      install dependencies
./run test      run the test suite
./run lint      check with ruff
./run check     lint and test, as CI does
```

## License

MIT. Copyright Hat Labs Oy.
