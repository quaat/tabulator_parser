from __future__ import annotations

from tabulator_parser.tab_model import (
    Section,
    TabScore,
    TabSystem,
    TimeSignature,
    Tuning,
)
from tabulator_parser.tab_render import render_tab


def test_render_tab_includes_header_sections_and_trims_trailing_spaces():
    system = TabSystem(
        tuning=Tuning(labels=["E"]),
        raw_lines=[
            "E|---0---|   ",
            "E|---1---|",
        ],
    )
    score = TabScore(
        title="A",
        artist="B",
        capo=2,
        sections=[
            Section(
                timestamp="1:23", time_signature=TimeSignature(3, 4), systems=[system]
            )
        ],
    )

    out = render_tab(score)

    assert out.endswith("\n")
    assert "title: A" in out
    assert "artist: B" in out
    assert "capo: 2" in out
    assert "1:23" in out
    assert "3/4" in out
    assert "E|---0---|" in out
    assert "E|---0---|   " not in out


def test_render_tab_without_capo_or_section_metadata():
    score = TabScore(
        title="No Capo", artist="Anon", capo=None, sections=[Section(systems=[])]
    )
    out = render_tab(score)
    assert "capo:" not in out
    assert out.splitlines()[0] == "title: No Capo"
