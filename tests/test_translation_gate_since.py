"""--since: gate on the staleness this change caused, not the repository's.

Without it the gate reads the whole repository, so one edit to an English page
cannot go green without every translation of it in the same change, and a page
someone left behind last month reddens a pull request that touched no
documentation at all.

--since narrows *stale* to the English pages that changed against a ref.
missing, unstamped and orphaned stay absolute: they are structural, and none of
them asks the author for translation work their change did not create.
"""

from __future__ import annotations

from conftest import DocsRepo

from halos_docs_tools import translation_status


def run(*argv: str) -> int:
    return translation_status.main(list(argv))


def test_a_page_this_change_did_not_touch_does_not_fail(docs_repo: DocsRepo):
    docs_repo.source("other.md")
    docs_repo.translation("fi", "other.md")
    docs_repo.translation("sv", "other.md")
    base = docs_repo.commit()

    # Someone else's page went stale earlier; this change edits nothing.
    docs_repo.source("other.md", "# Title\n\nEdited without translating.\n")
    docs_repo.commit()
    stale_base = docs_repo.git("rev-parse", "HEAD")

    docs_repo.write("unrelated.txt", "not documentation\n")

    assert run("--check") == 1
    assert run("--check", "--since", stale_base) == 0
    assert base  # the earlier state is what stale_base was measured against


def test_a_page_this_change_edited_still_fails(docs_repo: DocsRepo):
    base = docs_repo.commit()
    docs_repo.source("index.md", "# Title\n\nEdited in this change.\n")

    assert run("--check", "--since", base) == 1


def test_a_missing_translation_fails_however_old(docs_repo: DocsRepo):
    docs_repo.source("lonely.md")
    base = docs_repo.commit()
    docs_repo.write("unrelated.txt", "not documentation\n")

    assert run("--check", "--since", base) == 1


def test_an_unstamped_translation_fails_however_old(docs_repo: DocsRepo):
    docs_repo.translation("fi", "index.md", stamp=None)
    base = docs_repo.commit()
    docs_repo.write("unrelated.txt", "not documentation\n")

    assert run("--check", "--since", base) == 1


def test_an_orphaned_translation_fails_however_old(docs_repo: DocsRepo):
    # An orphan has no English source left, so it cannot be stamped from one.
    docs_repo.translation("fi", "gone.md", stamp="0" * 40)
    base = docs_repo.commit()
    docs_repo.write("unrelated.txt", "not documentation\n")

    assert run("--check", "--since", base) == 1


def test_what_was_not_gated_on_is_stated(docs_repo: DocsRepo, capsys):
    docs_repo.source("other.md")
    docs_repo.translation("fi", "other.md")
    docs_repo.translation("sv", "other.md")
    docs_repo.source("other.md", "# Title\n\nEdited without translating.\n")
    base = docs_repo.commit()

    assert run("--check", "--since", base) == 0
    out = capsys.readouterr().out
    assert "other.md" in out
    # A green run that quietly forgave two stale translations reads exactly
    # like a repository with none.
    assert "2" in out and "not gated on" in out


def test_a_ref_that_does_not_resolve_is_not_a_pass(docs_repo: DocsRepo, capsys):
    docs_repo.source("index.md", "# Title\n\nEdited in this change.\n")

    assert run("--check", "--since", "no-such-ref") == 2
    assert "no-such-ref" in capsys.readouterr().out


def test_since_on_a_plain_report_is_refused(docs_repo: DocsRepo, capsys):
    # The report shows everything by design, so --since would change nothing.
    # Silently inert is worse: the caller believes it scoped something.
    assert run("--since", "HEAD") == 2
    out = capsys.readouterr().out
    assert "--check" in out and "--comment" in out


def test_the_comment_omits_what_the_gate_excused(docs_repo: DocsRepo, capsys):
    """The comment body is the verdict, so it must agree with the verdict.

    render_comment covers every entry the gate fails on. Under --since the gate
    fails on fewer, and a comment naming a page the run passed on sends its
    author to translate something nobody asked them for.
    """
    docs_repo.source("stale-already.md")
    docs_repo.translation("fi", "stale-already.md")
    docs_repo.translation("sv", "stale-already.md")
    docs_repo.source("stale-already.md", "# Title\n\nEdited without translating.\n")
    base = docs_repo.commit()

    assert run("--comment", "--check", "--since", base) == 0
    body = capsys.readouterr().out
    assert "stale-already.md" not in body
    assert "not gated on" not in body


def test_the_comment_can_be_scoped_without_gating(docs_repo: DocsRepo, capsys):
    """The workflow's comment step wants the scope, not the exit status."""
    docs_repo.source("stale-already.md")
    docs_repo.translation("fi", "stale-already.md")
    docs_repo.translation("sv", "stale-already.md")
    docs_repo.source("stale-already.md", "# Title\n\nEdited without translating.\n")
    base = docs_repo.commit()

    assert run("--comment", "--since", base) == 0
    assert "stale-already.md" not in capsys.readouterr().out


def test_the_comment_still_names_what_this_change_broke(docs_repo: DocsRepo, capsys):
    base = docs_repo.commit()
    docs_repo.source("index.md", "# Title\n\nEdited in this change.\n")

    assert run("--comment", "--check", "--since", base) == 1
    assert "index.md" in capsys.readouterr().out
