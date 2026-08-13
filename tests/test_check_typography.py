"""Behaviour of the per-language typography checker."""

from __future__ import annotations

from conftest import DocsRepo

from halos_docs_tools import check_typography

NARROW_NBSP = "\u202f"


def run(*argv: str) -> int:
    return check_typography.main(list(argv))


def test_correctly_nested_guillemets_are_not_a_reversed_pair(
    docs_repo: DocsRepo, capsys
):
    """The false positive that motivated the alternation logic.

    Searching for the pair »…« in Norwegian matches the gap *between* two
    correct «…» quotations.
    """
    docs_repo.write("docs/nb/index.md", "Se «her» og «der» i teksten.\n")
    assert run("nb") == 0
    assert "quote faults 0" in capsys.readouterr().out


def test_outward_marks_in_norwegian_are_faults(docs_repo: DocsRepo, capsys):
    docs_repo.write("docs/nb/index.md", "Se »her« i teksten.\n")
    assert run("nb") == 1
    assert "closes nothing" in capsys.readouterr().out


def test_danish_uses_the_outward_pair(docs_repo: DocsRepo, capsys):
    docs_repo.write("docs/da/index.md", "Se »her« i teksten.\n")
    assert run("da") == 0
    assert "quote faults 0" in capsys.readouterr().out


def test_unclosed_quotation_is_reported(docs_repo: DocsRepo, capsys):
    docs_repo.write("docs/nb/index.md", "Se «her i teksten.\n")
    assert run("nb") == 1
    assert "never closed" in capsys.readouterr().out


def test_odd_number_of_symmetric_marks_is_reported(docs_repo: DocsRepo, capsys):
    docs_repo.write("docs/fi/index.md", "Katso ”tästä ja tuosta.\n")
    assert run("fi") == 1
    assert "odd number of" in capsys.readouterr().out


def test_space_before_a_colon_inside_a_code_fence_is_not_a_fault(
    docs_repo: DocsRepo, capsys
):
    """The second false positive: English comments inside code fences."""
    docs_repo.write(
        "docs/fi/index.md",
        "Katso:\n\n```\nnote : this is code\n```\n",
    )
    assert run("fi") == 0
    assert "spacing 0" in capsys.readouterr().out


def test_space_before_a_colon_in_prose_is_a_fault(docs_repo: DocsRepo, capsys):
    docs_repo.write("docs/fi/index.md", "Katso tätä : se on väärin.\n")
    assert run("fi") == 1
    assert "spacing 1" in capsys.readouterr().out


def test_french_requires_an_unbreakable_space_before_punctuation(
    docs_repo: DocsRepo, capsys
):
    docs_repo.write("docs/fr/index.md", f"Voyez ceci{NARROW_NBSP}: correct.\n")
    assert run("fr") == 0
    assert "spacing 0" in capsys.readouterr().out


def test_french_plain_space_before_punctuation_is_a_fault(docs_repo: DocsRepo, capsys):
    docs_repo.write("docs/fr/index.md", "Voyez ceci : incorrect.\n")
    assert run("fr") == 1
    assert "breakable space" in capsys.readouterr().out


def test_table_alignment_row_is_not_prose(docs_repo: DocsRepo, capsys):
    docs_repo.write(
        "docs/fi/index.md",
        "| Nimi | Arvo |\n| --- | ---: |\n| a | 1 |\n",
    )
    assert run("fi") == 0
    assert "spacing 0" in capsys.readouterr().out


def test_hyphen_chain_is_allowed_in_german_and_not_elsewhere(
    docs_repo: DocsRepo, capsys
):
    docs_repo.write("docs/de/index.md", "Das NMEA-2000-Netzwerk ist aktiv.\n")
    assert run("de") == 0
    docs_repo.write("docs/fi/index.md", "NMEA-2000-verkko on aktiivinen.\n")
    assert run("fi") == 1
    assert "hyphen inside a product name" in capsys.readouterr().out


def test_junction_hyphen_is_a_fault_in_the_romance_languages(
    docs_repo: DocsRepo, capsys
):
    docs_repo.write("docs/es/index.md", "La HaLOS-imagen se instala.\n")
    assert run("es") == 1
    assert "junction hyphen" in capsys.readouterr().out
    docs_repo.write("docs/nb/index.md", "HaLOS-avbilder installeres.\n")
    assert run("nb") == 0


def test_filenames_are_not_read_as_compounds(docs_repo: DocsRepo, capsys):
    docs_repo.write("docs/fi/index.md", "Lataa HALPI2-schematic_v0.6.1.pdf tiedosto.\n")
    assert run("fi") == 0


def test_a_named_locale_with_no_pages_is_not_a_pass(docs_repo: DocsRepo, capsys):
    """A renamed locale directory would otherwise silence the checker."""
    import shutil

    shutil.rmtree(docs_repo.root / "docs/fi")
    assert run("fi") == 2
    assert "no pages" in capsys.readouterr().err


def test_no_arguments_checks_the_locales_that_exist(docs_repo: DocsRepo, capsys):
    """The fixture has fi and sv on disk; the other seven rules have nothing."""
    docs_repo.write("docs/nb/index.md", "Se «her» i teksten.\n")
    assert run() == 0
    out = capsys.readouterr().out
    for present in ("fi", "sv", "nb"):
        assert f"{present}: " in out
    assert "de: " not in out


def test_no_locale_directory_at_all_is_not_a_pass(docs_repo: DocsRepo, capsys):
    import shutil

    for locale in ("fi", "sv"):
        shutil.rmtree(docs_repo.root / f"docs/{locale}")
    assert run() == 2
    assert "no pages" in capsys.readouterr().err
