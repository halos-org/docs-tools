"""Rewrite English anchor fragments in a translation to the translated slugs.

Anchor slugs come from heading text, so a translated heading gets a different
slug and every link pointing at it breaks — including links on pages nobody
touched. Translators leave the English fragment in place; this maps it across.

The mapping is positional: the structure comparison already proves the
translation has the same headings in the same order, so the nth heading of the
source page and the nth heading of the translation are the same heading. That is
stronger than matching on text, which cannot work once the text is in another
language.

    map-anchors site fi --apply

Without --apply it only reports what it would change.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .translation_status import configured_languages

HEADING_ID = re.compile(r"<h[1-6] id=\"([^\"]+)\"")
LINK = re.compile(r"\]\(([^)\s]*#[^)\s]+)\)")


def built_ids(site: Path, language: str, page: str, default: str) -> list[str]:
    """Heading ids of a built page, in document order.

    The default language has no URL segment of its own — its `index.md` is
    served at the site root, not under a locale directory — so source pages are
    looked up without a prefix.
    """
    stem = page[: -len(".md")]
    stem = "" if stem == "index" else stem.removesuffix("/index")
    prefix = "" if language == default else language
    parts = [p for p in (prefix, stem) if p]
    html = site.joinpath(*parts, "index.html")
    if not html.exists():
        raise SystemExit(
            f"No built page for {language}/{page} at {html} — build the site first."
        )
    return HEADING_ID.findall(html.read_text(encoding="utf-8"))


def target_page(link: str, page: str) -> str | None:
    """The markdown page a link points at, relative to the docs root."""
    path, _, _ = link.partition("#")
    if link.startswith(("http://", "https://", "mailto:")):
        return None
    if not path:
        return page
    resolved = (Path(page).parent / path).as_posix()
    resolved = Path(resolved).resolve().relative_to(Path.cwd().resolve()).as_posix()
    return resolved if resolved.endswith(".md") else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path, help="the built site directory")
    parser.add_argument("language", help="the locale directory to rewrite")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the changes; without it, only report them",
    )
    args = parser.parse_args(argv)

    default, _ = configured_languages()
    docs = Path("docs")

    sources = {
        p.relative_to(docs / default).as_posix(): built_ids(
            args.site, default, p.relative_to(docs / default).as_posix(), default
        )
        for p in (docs / default).rglob("*.md")
    }
    translated = {
        page: built_ids(args.site, args.language, page, default) for page in sources
    }

    changes, unmapped = [], []
    for page in sorted(sources):
        source = docs / args.language / page
        if not source.exists():
            continue
        text = original = source.read_text(encoding="utf-8")
        for link in set(LINK.findall(text)):
            path, _, fragment = link.partition("#")
            target = target_page(link, page)
            if target is None or target not in sources:
                continue
            ids_source, ids_translated = sources[target], translated[target]
            if fragment not in ids_source:
                continue
            if len(ids_source) != len(ids_translated):
                unmapped.append(
                    f"{args.language}/{page} -> {link}: {target} has "
                    f"{len(ids_source)} headings in {default}, "
                    f"{len(ids_translated)} translated"
                )
                continue
            replacement = ids_translated[ids_source.index(fragment)]
            if replacement != fragment:
                text = text.replace(f"]({link})", f"]({path}#{replacement})")
                changes.append(
                    f"  {args.language}/{page}\n      {fragment}  ->  {replacement}"
                )
        if text != original and args.apply:
            source.write_text(text, encoding="utf-8")

    verb = "rewritten" if args.apply else "to rewrite"
    print(f"{len(changes)} anchors {verb} in docs/{args.language}.")
    for change in changes:
        print(change)
    if unmapped:
        print(f"\n{len(unmapped)} could not be mapped — structure differs:")
        for problem in unmapped:
            print(f"  {problem}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
