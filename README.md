# halos-docs-tools

Documentation checkers for HaLOS and Hat Labs MkDocs sites: translation status,
stamping, anchor validation, glossary and typography checks.

The same code runs in CI and on a laptop. Every check a pull request must pass is
runnable before you push.

## Installing

Add it to a documentation repository's `pyproject.toml`, pinned to a tag:

```toml
dependencies = [
    "halos-docs-tools @ git+https://github.com/halos-org/docs-tools@vX.Y.Z",
]
```

Use a tag from the [releases page](https://github.com/halos-org/docs-tools/releases).
`uv sync` then puts all six commands on the path. Each repository pins its own
version; upgrading is a deliberate edit to that pin.

`git` must be on the path. `translation-status`, `stamp-translation` and
`check-glossary` shell out to it, and it is not something a Python dependency
can bring.

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

### Exit statuses

A workflow branches on these, so they are part of the interface.

| Status | Meaning |
|:---|:---|
| 0 | the check passed |
| 1 | the check found problems — broken anchors, unused glossary terms, typography faults, or (with `--check`) translations that are not current |
| 2 | the check could not run: `check-anchors` was given a site directory holding no built pages |

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

`--only-pages` narrows the report and never the rule.

### Gating on the staleness this change caused

```
translation-status --check --since origin/main
```

Whole-repository `--check` has a cost that shows up the first time someone
fixes a typo: editing one English page marks every translation of it stale, so
the change cannot go green until all of them land in the same pull request. And
a page somebody left behind last month fails a pull request that touched no
documentation at all.

`--since REF` gates on `stale` only for English pages whose content differs
from `REF`. `missing`, `unstamped` and `orphaned` still fail wherever they came
from — those are structural, and none of them asks an author for translation
work their change did not create.

What it passed over is printed, so a green run is not mistaken for a clean
repository. If `REF` does not resolve — an unknown ref, or a clone too shallow
to hold it — the command exits 2 rather than forgiving everything it could not
measure.

One consequence is worth knowing before you meet it: adding a locale to
`mkdocs.yml` makes every page `missing` in that locale immediately. A new
locale therefore arrives in a single pull request, together with its pages.

### The pull request comment

```
translation-status --comment > body.md
```

writes a comment body describing every entry the gate fails on, with the
English changes since each translation was written, collapsed. The command
writes a body and nothing else; posting it belongs to whatever holds the token.

The body carries a `<!-- translation-status -->` marker so a workflow can find
and update its own previous comment rather than adding another one. If the body
would exceed GitHub's 65536-character limit, the diffs come out and the reader
is pointed at the job summary for them.

## Development

```
./run deps      install dependencies
./run test      run the test suite
./run lint      check with ruff
./run check     lint and test, as CI does
```

## License

MIT. Copyright Hat Labs Oy.
