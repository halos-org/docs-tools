"""Report which translations are missing or out of date.

A translation records the git blob hash of the English source it was written
against, in its own frontmatter:

    ---
    translated_from: <blob hash of docs/en/<path> at translation time>
    ---

The English page carries nothing, so an English edit needs no ceremony: editing
it changes its content, which changes its hash, which makes every translation of
it report as stale on its own.

Reports by default. With --check it also fails: any page that is not current,
in any configured locale, exits non-zero. That is a property of the repository,
so the gate ignores --only-pages, which narrows the report and not the rule.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

DOCS = Path("docs")
STAMP_KEY = "translated_from"
# What mkdocs treats as a page. Enumerating only *.md leaves the rest published
# in every locale carrying the default language's text, with nothing to report
# them: they are not missing translations, they are pages nobody looked at.
MARKDOWN = (".md", ".markdown", ".mdown", ".mkdn", ".mkd")
# GitHub rejects a comment body over 65536 characters with HTTP 422. A wide
# change produces a report far beyond that, so the diffs come out below this
# and the reader is sent to the job summary for them.
COMMENT_CEILING = 60000
COMMENT_MARKER = "<!-- translation-status -->"


class _Loader(yaml.SafeLoader):
    """mkdocs.yml carries python/name tags that SafeLoader refuses to parse."""


_Loader.add_multi_constructor("", lambda loader, suffix, node: None)


def configured_languages() -> tuple[str, list[str]]:
    """Return (default language, other languages) from the i18n plugin config."""
    config = yaml.load(Path("mkdocs.yml").read_text(encoding="utf-8"), Loader=_Loader)
    for plugin in config.get("plugins", []):
        if isinstance(plugin, dict) and "i18n" in plugin:
            languages = plugin["i18n"]["languages"]
            default = next(lang["locale"] for lang in languages if lang.get("default"))
            others = [lang["locale"] for lang in languages if not lang.get("default")]
            return default, others
    raise SystemExit("mkdocs.yml has no i18n plugin configuration")


def blob_hash(path: Path) -> str:
    return subprocess.run(
        # --no-filters: without it the hash is of the content after eol and
        # .gitattributes filtering, so the stamp moves when repository or
        # client configuration changes and no page does. Adding `* text=auto`
        # would flip every translation to stale at once.
        ["git", "hash-object", "--no-filters", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def stamp_of(path: Path) -> str | None:
    """Read translated_from from a page's frontmatter, if it has one."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    front = yaml.safe_load(text[4:end]) or {}
    value = front.get(STAMP_KEY)
    return str(value) if value else None


@cache
def english_diff(stamped: str, current: Path) -> str | None:
    """Diff the stamped English blob against the English page as it stands now.

    The current page is compared from the working tree rather than as a stored
    object: `git hash-object` computes a hash without writing the object, so
    diffing two hashes would fail on the side that was never stored.

    Cached because the answer is a property of the page and the stamp, not of
    the locale asking. Nine locales stamped against the same blob would
    otherwise each pay a `git cat-file`, a `git diff` and a temporary
    directory for identical output.
    """
    blob = subprocess.run(
        ["git", "cat-file", "-p", stamped],
        capture_output=True,
        text=True,
    )
    if blob.returncode != 0:
        return None  # stamped blob not in this clone — CI needs fetch-depth: 0
    with tempfile.TemporaryDirectory() as tmp:
        was = Path(tmp) / current.name
        was.write_text(blob.stdout, encoding="utf-8")
        result = subprocess.run(
            ["git", "diff", "--no-index", "--no-color", str(was), str(current)],
            capture_output=True,
            text=True,
        )
    # --no-index exits 1 when the files differ, which is the expected case.
    # Drop the file headers: they carry a temporary path, and the page is
    # already named in the surrounding report.
    noise = ("diff --git ", "index ", "--- ", "+++ ")
    return "\n".join(
        line for line in result.stdout.splitlines() if not line.startswith(noise)
    )


@dataclass
class Entry:
    language: str
    page: str  # path relative to the language directory
    state: str  # missing | unstamped | stale | orphaned | current
    expected: str  # blob hash the translation should record
    diff: str | None = None


def pages_under(root: Path) -> list[Path]:
    """Every markdown page mkdocs would publish from this directory.

    os.walk with followlinks, not rglob: mkdocs walks the docs tree following
    symlinks, so a linked directory of shared pages is built and served. rglob
    does not descend into one, which would leave those pages unexamined while
    the report showed nothing wrong.
    """
    found: list[Path] = []
    for directory, _, names in os.walk(root, followlinks=True):
        found += [Path(directory) / name for name in names if name.endswith(MARKDOWN)]
    return sorted(found)


def unclassified_pages(default: str, languages: list[str]) -> list[Path]:
    """Markdown under docs/ that belongs to no configured locale.

    mkdocs-static-i18n serves such a page under every locale, untranslated.
    Whether it should be translated is a question about the page, which this
    tool cannot answer -- so it reports them rather than passing over them.
    """
    locales = {default, *languages}
    return [
        page
        for page in pages_under(DOCS)
        if page.relative_to(DOCS).parts[0] not in locales
    ]


def collect(default: str, languages: list[str], want_diff: bool) -> list[Entry]:
    sources = pages_under(DOCS / default)
    entries: list[Entry] = []
    for source in sources:
        relative = source.relative_to(DOCS / default)
        expected = blob_hash(source)
        for language in languages:
            target = DOCS / language / relative
            if not target.exists():
                entries.append(Entry(language, str(relative), "missing", expected))
                continue
            stamped = stamp_of(target)
            if stamped is None:
                entries.append(Entry(language, str(relative), "unstamped", expected))
            elif stamped == expected:
                entries.append(Entry(language, str(relative), "current", expected))
            else:
                diff = english_diff(stamped, source) if want_diff else None
                entries.append(Entry(language, str(relative), "stale", expected, diff))

    # A translation whose source was deleted is invisible to the loop above,
    # because that walks the sources. It is still a page being served.
    for language in languages:
        root = DOCS / language
        for translation in pages_under(root):
            if not (DOCS / default / translation.relative_to(root)).exists():
                entries.append(
                    Entry(language, str(translation.relative_to(root)), "orphaned", "")
                )
    return entries


def render_text(entries: list[Entry]) -> str:
    out = []
    for language in sorted({e.language for e in entries}):
        rows = [e for e in entries if e.language == language]
        counts = {
            s: sum(1 for e in rows if e.state == s)
            for s in ("current", "stale", "unstamped", "missing", "orphaned")
        }
        out.append(f"{language}: " + "  ".join(f"{k}={v}" for k, v in counts.items()))
        for entry in rows:
            if entry.state != "current":
                out.append(f"  {entry.state:9s} {entry.page}")
                if entry.expected:
                    out.append(f"    {STAMP_KEY}: {entry.expected}")
    return "\n".join(out)


def render_markdown(entries: list[Entry], only: set[str] | None) -> str:
    shown = [e for e in entries if only is None or e.page in only]
    out = ["## Translation status", ""]
    for language in sorted({e.language for e in entries}):
        rows = [e for e in entries if e.language == language]
        counts = {
            s: sum(1 for e in rows if e.state == s)
            for s in ("current", "stale", "unstamped", "missing", "orphaned")
        }
        summary = ", ".join(f"{v} {k}" for k, v in counts.items() if v)
        out.append(f"**{language}** — {summary}")
    out.append("")

    behind = [e for e in shown if e.state != "current"]
    if not behind:
        out.append("Every translation of the pages in scope is current.")
        return "\n".join(out)

    out += [
        "| Language | Page | State | Stamp to record |",
        "|:---|:---|:---|:---|",
    ]
    for entry in behind:
        out.append(
            f"| {entry.language} | `{entry.page}` | {entry.state} | `{entry.expected}` |"
        )
    out.append("")

    for entry in behind:
        if entry.diff:
            out += [
                f"<details><summary>English changes since "
                f"<code>{entry.language}/{entry.page}</code> was translated</summary>",
                "",
                "```diff",
                entry.diff.rstrip(),
                "```",
                "",
                "</details>",
                "",
            ]
        elif entry.state == "stale":
            out.append(
                f"<!-- {entry.page}: stamped blob not in this clone; "
                f"CI needs fetch-depth: 0 -->"
            )
    return "\n".join(out)


def render_comment(entries: list[Entry]) -> str:
    """The pull request comment body: every entry the gate fails on.

    Scoping this to the pages a pull request touched would let the comment omit
    the page that turned the check red, because the gate reads the whole
    repository and a diff does not.
    """
    full = render_markdown(entries, None)
    if len(full) <= COMMENT_CEILING:
        return f"{full}\n\n{COMMENT_MARKER}\n"

    without_diffs = render_markdown(
        [Entry(e.language, e.page, e.state, e.expected) for e in entries], None
    )
    return (
        f"{without_diffs}\n\n"
        "_Diffs omitted: the full report exceeds GitHub's comment size limit._\n"
        "_See the workflow run's job summary for the complete report._\n"
        f"\n{COMMENT_MARKER}\n"
    )


def changed_sources(ref: str, default: str) -> set[str] | None:
    """English pages differing from `ref`, relative to the language directory.

    None when the diff could not be computed -- an unknown ref, or a clone too
    shallow to contain it. The caller must not read that as "nothing changed":
    a gate that forgives every stale page because it could not tell which ones
    this change touched forgives the whole repository.
    """
    root = DOCS / default
    result = subprocess.run(
        ["git", "diff", "--name-only", ref, "--", str(root)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    changed = set()
    for line in result.stdout.splitlines():
        try:
            changed.add(str(Path(line).relative_to(root)))
        except ValueError:
            continue
    return changed


def render_excused(excused: list[Entry], ref: str) -> str:
    """Say what the gate passed over, so a green run is not read as a clean one."""
    pages = sorted({e.page for e in excused})
    translations = f"{len(excused)} stale translation" + (
        "s" if len(excused) > 1 else ""
    )
    of_pages = f"{len(pages)} page" + ("s" if len(pages) > 1 else "")
    out = [
        "",
        f"{translations} of {of_pages} were already stale at {ref} and were "
        "not gated on:",
        "",
    ]
    out += [f"  {page}" for page in pages]
    out += [
        "",
        "They are still in the report above, and still block whichever change "
        "edits their English source next.",
    ]
    return "\n".join(out)


def render_failure(behind: list[Entry]) -> str:
    """Name every entry the gate is failing on.

    A non-zero exit carrying only a count sends the reader into the job log to
    find out what to do, and the report above may have been filtered to a
    subset of pages. This block is the one thing that always lists all of it.
    """
    out = [
        "",
        f"Translation gate: {len(behind)} of the configured translations are "
        f"not current.",
        "",
    ]
    for entry in sorted(behind, key=lambda e: (e.state, e.language, e.page)):
        out.append(f"  {entry.state:9s} {entry.language}/{entry.page}")
    out += [
        "",
        "Translate the pages above, stamp them with stamp-translation, and "
        "run this check again.",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("text", "markdown"), default="text")
    parser.add_argument(
        "--diff",
        action="store_true",
        help="include the English diff for stale pages",
    )
    parser.add_argument(
        "--only-pages",
        nargs="*",
        metavar="PATH",
        help="restrict the detail section to these docs/<lang>/-relative paths",
    )
    parser.add_argument(
        "--comment",
        action="store_true",
        help="emit a pull request comment body covering every entry the gate "
        "fails on, size-capped, instead of the report",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero when any translation is stale, missing, unstamped "
        "or orphaned, across the whole repository",
    )
    parser.add_argument(
        "--since",
        metavar="REF",
        help="gate on stale translations only for English pages that changed "
        "since REF. Missing, unstamped and orphaned still fail whatever "
        "change introduced them",
    )
    args = parser.parse_args(argv)

    if args.since and not args.check:
        print("--since narrows what --check fails on, so it needs --check.")
        return 2

    default, languages = configured_languages()
    if not languages:
        print("No translation languages configured.")
        # Reporting nothing is fine. Gating on nothing is not: the check would
        # pass because it had no work, which reads exactly like passing.
        return 2 if args.check else 0

    entries = collect(default, languages, want_diff=args.diff or args.comment)
    if args.comment:
        print(render_comment(entries))
    elif args.format == "markdown":
        only = set(args.only_pages) if args.only_pages else None
        print(render_markdown(entries, only))
    else:
        print(render_text(entries))

    if args.check:
        # Exit 2 for "the check could not run over everything", distinct from
        # 1 for "the check found stale translations". A gate that reports
        # success over content it never examined is worse than no gate.
        if not pages_under(DOCS / default):
            print(
                f"\nFound no source pages under {DOCS / default}. Nothing was checked."
            )
            return 2
        stray = unclassified_pages(default, languages)
        if stray:
            print(
                "\nThe check cannot classify these pages: they are under "
                f"{DOCS} but in none of the configured locales "
                f"({', '.join(sorted({default, *languages}))}), and mkdocs "
                "serves such a page under every locale untranslated.\n"
            )
            for page in stray:
                print(f"  {page}")
            print(
                "\nMove each one into a locale directory, or exclude it from "
                "the documentation tree."
            )
            return 2

        behind = [e for e in entries if e.state != "current"]

        if args.since:
            changed = changed_sources(args.since, default)
            if changed is None:
                print(
                    f"\nCannot diff against '{args.since}'. The gate was asked "
                    "to fail only on what this change made stale, and it "
                    "cannot tell what that is.\n\nCheck the ref exists in this "
                    "clone -- a shallow checkout is the usual cause."
                )
                return 2
            excused = [
                e for e in behind if e.state == "stale" and e.page not in changed
            ]
            if excused:
                print(render_excused(excused, args.since))
                behind = [e for e in behind if e not in excused]

        if behind:
            print(render_failure(behind))
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
