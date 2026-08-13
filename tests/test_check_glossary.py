"""Behaviour of the glossary-adherence checker."""

from __future__ import annotations

from conftest import DocsRepo

from halos_docs_tools import check_glossary


def glossary(repo: DocsRepo, *rows: tuple[str, str]) -> None:
    table = ["| English | Finnish |", "|:---|:---|"]
    table += [f"| {source} | {target} |" for source, target in rows]
    repo.write("solutions/translation/finnish-glossary.md", "\n".join(table) + "\n")


def run(*argv: str) -> int:
    return check_glossary.main(list(argv))


def test_prescribed_term_in_use_passes(docs_repo: DocsRepo, capsys):
    glossary(docs_repo, ("power supply", "virtalähde"))
    docs_repo.source("index.md", "The power supply is fine. The power supply works.\n")
    docs_repo.write("docs/fi/index.md", "Virtalähde on kunnossa.\n")
    assert run("fi") == 0
    out = capsys.readouterr().out
    assert "Checked 1 glossary terms" in out
    assert "Every prescribed term is in use." in out


def test_prescribed_term_never_used_is_reported(docs_repo: DocsRepo, capsys):
    glossary(docs_repo, ("power supply", "virtalähde"))
    docs_repo.source("index.md", "The power supply is fine. The power supply works.\n")
    docs_repo.write("docs/fi/index.md", "Teholähde on kunnossa.\n")
    assert run("fi") == 1
    out = capsys.readouterr().out
    assert "prescribed but unused" in out
    assert "power supply" in out


def test_a_term_used_once_in_english_is_not_checked(docs_repo: DocsRepo, capsys):
    glossary(docs_repo, ("power supply", "virtalähde"))
    docs_repo.source("index.md", "The power supply is fine.\n")
    docs_repo.write("docs/fi/index.md", "Teholähde on kunnossa.\n")
    assert run("fi") == 0
    assert "Checked 0 glossary terms" in capsys.readouterr().out


def test_occurrences_inside_a_code_fence_do_not_count(docs_repo: DocsRepo, capsys):
    glossary(docs_repo, ("power supply", "virtalähde"))
    docs_repo.source(
        "index.md",
        "Intro.\n\n```\n# power supply\n# power supply\n```\n",
    )
    docs_repo.write("docs/fi/index.md", "Teholähde on kunnossa.\n")
    assert run("fi") == 0
    assert "Checked 0 glossary terms" in capsys.readouterr().out


def test_an_inflected_form_counts_as_used(docs_repo: DocsRepo, capsys):
    glossary(docs_repo, ("power supply", "virtalähde"))
    docs_repo.source("index.md", "The power supply is fine. The power supply works.\n")
    docs_repo.write("docs/fi/index.md", "Virtalähteen jännite on oikea.\n")
    assert run("fi") == 0
    assert "Every prescribed term is in use." in capsys.readouterr().out


def test_a_longer_compound_does_not_satisfy_the_term(docs_repo: DocsRepo, capsys):
    """The false green the word boundary exists to prevent.

    Finnish `virtalähde` is a substring of `vakiovirtalähde`, a different
    component. A checker that passes when it should not is no checker at all.
    """
    glossary(docs_repo, ("power supply", "virtalähde"))
    docs_repo.source("index.md", "The power supply is fine. The power supply works.\n")
    docs_repo.write("docs/fi/index.md", "Vakiovirtalähde on kytketty.\n")
    assert run("fi") == 1
    assert "prescribed but unused" in capsys.readouterr().out


def test_alternatives_separated_by_a_slash_each_satisfy_the_row(
    docs_repo: DocsRepo, capsys
):
    glossary(docs_repo, ("power supply", "virtalähde / syöttöjännite"))
    docs_repo.source("index.md", "The power supply is fine. The power supply works.\n")
    docs_repo.write("docs/fi/index.md", "Syöttöjännite on oikea.\n")
    assert run("fi") == 0


def test_header_and_separator_rows_are_not_terms(docs_repo: DocsRepo, capsys):
    glossary(docs_repo, ("power supply", "virtalähde"))
    docs_repo.source("index.md", "The power supply is fine. The power supply works.\n")
    docs_repo.write("docs/fi/index.md", "Virtalähde on kunnossa.\n")
    assert run("fi") == 0
    # One data row, not three: the header and the alignment row are markup.
    assert "Checked 1 glossary terms" in capsys.readouterr().out


def test_a_glossary_with_no_data_rows_is_not_a_pass(docs_repo: DocsRepo, capsys):
    glossary(docs_repo)
    docs_repo.source("index.md", "Nothing here.\n")
    docs_repo.write("docs/fi/index.md", "Ei mitään.\n")
    assert run("fi") == 2
    assert "defines no terms" in capsys.readouterr().err


def test_a_corpus_where_no_term_meets_the_thresholds_still_passes(
    docs_repo: DocsRepo, capsys
):
    """A quiet run is not a broken one, but it must say which it was."""
    glossary(docs_repo, ("power supply", "virtalähde"))
    docs_repo.source("index.md", "The power supply is fine.\n")
    docs_repo.write("docs/fi/index.md", "Teholähde on kunnossa.\n")
    assert run("fi") == 0
    assert "No term met the thresholds" in capsys.readouterr().out


def test_source_locale_comes_from_mkdocs_not_a_hard_coded_en(
    docs_repo: DocsRepo, capsys
):
    """The package cannot assume the source locale is English."""
    docs_repo.write(
        "mkdocs.yml",
        """\
        site_name: Test docs
        plugins:
          - i18n:
              docs_structure: folder
              languages:
                - locale: sv
                  name: Svenska
                  default: true
                - locale: fi
                  name: Suomi
        """,
    )
    glossary(docs_repo, ("power supply", "virtalähde"))
    docs_repo.write(
        "docs/sv/index.md", "The power supply works. The power supply is on.\n"
    )
    docs_repo.write("docs/fi/index.md", "Teholähde on kunnossa.\n")
    assert run("fi") == 1
    assert "prescribed but unused" in capsys.readouterr().out


def test_checking_no_terms_at_all_is_not_a_pass(docs_repo: DocsRepo, capsys):
    """Exit 0 must mean "checked and passed", never "looked at nothing".

    A renamed source directory would otherwise print the same success line a
    correct run prints, with nothing in the log to tell them apart.
    """
    glossary(docs_repo, ("power supply", "virtalähde"))
    (docs_repo.root / "docs/en").rename(docs_repo.root / "docs/english")
    assert run("fi") == 2
    assert "No source pages" in capsys.readouterr().err
