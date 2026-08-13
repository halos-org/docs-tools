"""Verify that every internal anchor in the built site resolves to a real id.

Anchors are generated from heading text, so translating a heading changes its
slug and silently breaks every link pointing at it — including links on pages
that were not touched, which is why this is a delayed fault: a cross-page anchor
keeps working until its *target* page is translated. `mkdocs build --strict`
does not validate anchors at all.

Run against a built site directory. Exit status is 1 if any anchor is broken.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urldefrag, urlsplit

import yaml

HREF = re.compile(r'href="([^"]+)"')
ID = re.compile(r'\sid="([^"]+)"')


class _Loader(yaml.SafeLoader):
    """mkdocs.yml carries python/name tags that SafeLoader refuses to parse."""


_Loader.add_multi_constructor("", lambda loader, suffix, node: None)


def configured_base() -> str:
    """The path component of site_url, for resolving root-absolute links.

    A base that does not match the site makes every root-absolute link look
    like somebody else's, so the checker skips them and reports a pass it did
    not earn. Reading it from the same file the build reads keeps the two from
    disagreeing.
    """
    config_path = Path("mkdocs.yml")
    if not config_path.exists():
        return "/"
    config = yaml.load(config_path.read_text(encoding="utf-8"), Loader=_Loader) or {}
    site_url = config.get("site_url")
    if not site_url:
        return "/"
    path = urlsplit(str(site_url)).path or "/"
    return path if path.endswith("/") else path + "/"


def collect_pages(
    site: str, exclude: list[str]
) -> tuple[dict[str, set[str]], set[str]]:
    """Map each built page to the ids it defines, and note which are excluded.

    An excluded page contributes no links to the check but keeps its ids: it is
    still a page other pages may legitimately link into.
    """
    ids: dict[str, set[str]] = {}
    excluded: set[str] = set()
    for root, _, files in os.walk(site):
        for name in files:
            if not name.endswith(".html"):
                continue
            path = os.path.join(root, name)
            real = os.path.realpath(path)
            with open(path, encoding="utf-8") as handle:
                ids[real] = set(ID.findall(handle.read()))
            relative = os.path.relpath(path, site)
            if any(fnmatch.fnmatch(relative, pattern) for pattern in exclude):
                excluded.add(real)
    return ids, excluded


def resolve(href: str, page: str, site: str, base: str) -> str | None:
    """Resolve an href to the built file it points at, or None if not ours."""
    target, _ = urldefrag(href)
    target = unquote(target)
    if not target:
        return os.path.realpath(page)
    if target.startswith("/"):
        # The base always carries a trailing slash, so a link to the site root
        # written without one -- /halpi2#section -- fails startswith and would
        # be skipped as somebody else's. Skipping is the silent pass this
        # module exists to prevent.
        if target == base.rstrip("/"):
            path = site
        elif not target.startswith(base):
            return None
        else:
            path = os.path.normpath(os.path.join(site, target[len(base) :]))
    else:
        path = os.path.normpath(os.path.join(os.path.dirname(page), target))
    if not path.endswith(".html"):
        path = os.path.join(path, "index.html")
    return os.path.realpath(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", nargs="?", default="site")
    parser.add_argument(
        "--base",
        help="path component of site_url, for root-absolute links "
        "(default: read from mkdocs.yml)",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        metavar="PATTERN",
        help="skip links on built pages matching these glob patterns, relative "
        "to the site directory. Their own ids stay linkable. Generated "
        "single-page exports need this",
    )
    args = parser.parse_args(argv)
    # The same normalisation configured_base() applies. Without it, --base
    # /halpi2 strips one character too few and every root-absolute link
    # resolves outside the built tree, reported as breakage that is not there.
    base = args.base if args.base is not None else configured_base()
    if not base.endswith("/"):
        base += "/"

    ids, excluded = collect_pages(args.site, args.exclude)
    if not ids:
        # Passing on an empty site would be a false green: the build produced
        # nothing, or the path is wrong, and neither is "all anchors resolve".
        print(
            f"No built pages found under {args.site!r} — nothing to check.",
            file=sys.stderr,
        )
        return 2

    if excluded == set(ids):
        # fnmatch crosses '/', so '*' and '*.html' both reach every page.
        # Silencing the whole site is the same false green the guard above
        # exists to prevent, reached by a pattern rather than a wrong path.
        print(
            f"every built page is excluded by {args.exclude} — nothing to check.",
            file=sys.stderr,
        )
        return 2

    broken: list[tuple[str, str, str]] = []
    checked = 0

    for page in sorted(ids):
        if page in excluded:
            continue
        with open(page, encoding="utf-8") as handle:
            hrefs = HREF.findall(handle.read())
        for href in hrefs:
            if href.startswith(("http://", "https://", "mailto:", "data:")):
                continue
            _, fragment = urldefrag(href)
            if not fragment:
                continue
            target = resolve(href, page, args.site, base)
            if target is None:
                continue
            checked += 1
            relative = os.path.relpath(page, args.site)
            if target not in ids:
                broken.append((relative, href, "target page does not exist"))
            elif unquote(fragment) not in ids[target]:
                broken.append((relative, href, "no such anchor on the target page"))

    skipped = f", {len(excluded)} excluded" if excluded else ""
    print(
        f"Checked {checked} anchor links across {len(ids) - len(excluded)} pages{skipped}."
    )
    if broken:
        print(f"\n{len(broken)} broken:\n")
        for page, href, why in broken:
            print(f"  {page}\n      -> {href}   ({why})")
        return 1
    print("All anchors resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
