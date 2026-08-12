"""The pull request comment body.

The comment has to describe exactly what the gate fails on. A red check whose
comment never mentions the offending page is worse than no comment: the reader
has nothing to act on.
"""

from __future__ import annotations

import re

from conftest import DocsRepo

from halos_docs_tools import translation_status

MARKER = "<!-- translation-status -->"


def run(*argv: str) -> int:
    return translation_status.main(list(argv))


def body(capsys) -> str:
    return capsys.readouterr().out


def named_in(text: str) -> set[tuple[str, str]]:
    """The (locale, page) pairs the comment table lists."""
    return set(re.findall(r"^\| (\w+) \| `([^`]+)` \|", text, flags=re.M))


def failing(docs_repo: DocsRepo) -> set[tuple[str, str]]:
    default, languages = translation_status.configured_languages()
    entries = translation_status.collect(default, languages, want_diff=False)
    return {(e.language, e.page) for e in entries if e.state != "current"}


def test_a_stale_page_is_described_in_full(docs_repo: DocsRepo, capsys):
    docs_repo.commit("docs: seed")
    docs_repo.source("index.md", "# Title\n\nEnglish body, revised.\n")
    assert run("--comment") == 0
    out = body(capsys)
    assert "| fi | `index.md` | stale |" in out
    assert docs_repo.blob("index.md") in out
    assert "+English body, revised." in out
    assert MARKER in out


def test_a_current_repository_still_produces_a_body(docs_repo: DocsRepo, capsys):
    assert run("--comment") == 0
    out = body(capsys)
    assert "Every translation" in out
    assert MARKER in out


def test_the_comment_covers_everything_the_gate_fails_on(docs_repo: DocsRepo, capsys):
    docs_repo.source("guide.md")
    docs_repo.source("index.md", "# Title\n\nRevised.\n")
    docs_repo.write("docs/fi/gone.md", "---\ntranslated_from: x\n---\n\nBody.\n")
    assert run("--comment") == 0
    assert named_in(body(capsys)) == failing(docs_repo)


def test_only_pages_does_not_narrow_the_comment(docs_repo: DocsRepo, capsys):
    """The comment answers for the gate, and the gate is repo-wide."""
    docs_repo.source("guide.md")
    docs_repo.source("index.md", "# Title\n\nRevised.\n")
    assert run("--comment", "--only-pages", "index.md") == 0
    assert named_in(body(capsys)) == failing(docs_repo)


def test_an_oversized_body_drops_the_diffs_and_points_at_the_summary(
    docs_repo: DocsRepo, capsys
):
    """GitHub rejects a comment body over 65536 characters with HTTP 422."""
    docs_repo.source("index.md", "# Title\n\n" + "original line\n" * 4000)
    docs_repo.translation("fi", "index.md")
    docs_repo.translation("sv", "index.md")
    docs_repo.commit("docs: seed")
    docs_repo.source("index.md", "# Title\n\n" + "replaced line\n" * 4000)

    assert run("--comment") == 0
    out = body(capsys)
    assert len(out) < 65536
    assert "```diff" not in out
    assert "Diffs omitted" in out
    assert "job summary" in out
    assert MARKER in out
    assert "| fi | `index.md` | stale |" in out


def test_a_body_that_fits_keeps_its_diffs(docs_repo: DocsRepo, capsys):
    docs_repo.commit("docs: seed")
    docs_repo.source("index.md", "# Title\n\nSmall change.\n")
    assert run("--comment") == 0
    out = body(capsys)
    assert "```diff" in out
    assert "Diffs omitted" not in out


def test_comment_and_check_compose(docs_repo: DocsRepo, capsys):
    docs_repo.source("index.md", "# Title\n\nRevised.\n")
    assert run("--comment", "--check") != 0
    out = body(capsys)
    assert MARKER in out
    assert "Translation gate:" in out
