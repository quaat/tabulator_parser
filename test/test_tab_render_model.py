from __future__ import annotations

from fractions import Fraction

import tabulator_parser.tab_render_model as renderer
from tabulator_parser.tab_model import (
    Barline,
    ChordEvent,
    Measure,
    NoteEvent,
    RestEvent,
    Section,
    TabScore,
    TabSystem,
    TimeSignature,
    Tuning,
)


def _make_measure(events, *, width=8):
    return Measure(
        barline_left=Barline.SINGLE,
        barline_right=Barline.SINGLE,
        time_signature=TimeSignature(4, 4),
        events=list(events),
        raw_columns=width,
    )


def test_render_tab_from_model_renders_duration_line_and_notes():
    measure = _make_measure(
        [
            ChordEvent(
                start=Fraction(0, 1),
                duration=Fraction(1, 1),
                notes=[
                    NoteEvent(
                        start=Fraction(0, 1),
                        duration=Fraction(1, 1),
                        string_index=0,
                        fret=3,
                    ),
                    NoteEvent(
                        start=Fraction(0, 1),
                        duration=Fraction(1, 1),
                        string_index=1,
                        fret=5,
                    ),
                ],
            ),
            RestEvent(start=Fraction(1, 1), duration=Fraction(1, 2)),
            NoteEvent(
                start=Fraction(3, 2), duration=Fraction(1, 4), string_index=0, fret=None
            ),
            NoteEvent(
                start=Fraction(7, 4),
                duration=Fraction(1, 4),
                string_index=1,
                fret=7,
                is_ghost=True,
            ),
        ],
        width=10,
    )
    system = TabSystem(tuning=Tuning(labels=["E", "B"]), measures=[measure])
    score = TabScore(
        title="Title",
        artist="Artist",
        capo=3,
        sections=[
            Section(
                timestamp="0:11", time_signature=TimeSignature(4, 4), systems=[system]
            )
        ],
    )

    out = renderer.render_tab_from_model(score)

    assert out.startswith("title: Title")
    assert "0:11" in out
    assert "4/4" in out
    assert "capo: 3" in out
    assert "E|" in out
    assert "B|" in out
    assert "x" in out
    assert "(" in out
    assert "Q" in out or "E" in out or "S" in out


def test_render_measure_unknown_rhythm_and_internal_helpers():
    measure = _make_measure(
        [
            NoteEvent(
                start=Fraction(70, 1), duration=Fraction(1, 1), string_index=0, fret=9
            ),
            NoteEvent(
                start=Fraction(71, 1), duration=Fraction(1, 1), string_index=1, fret=8
            ),
        ],
        width=120,
    )
    grid, duration_line = renderer._render_measure(measure, 2)
    assert duration_line is None
    assert any("9" in "".join(row) for row in grid)
    mapper_raw = renderer._make_time_to_col_mapper(measure, 120)
    assert mapper_raw(Fraction(71, 1)) == 71

    # _has_rhythm_mode edge branches.
    empty_measure = _make_measure([], width=6)
    assert renderer._has_rhythm_mode(empty_measure) is False

    # _make_time_to_col_mapper branch when total <= 0.
    zero_duration_measure = _make_measure(
        [
            NoteEvent(
                start=Fraction(0, 1), duration=Fraction(0, 1), string_index=0, fret=1
            )
        ],
        width=6,
    )
    mapper = renderer._make_time_to_col_mapper(zero_duration_measure, 6)
    assert 0 <= mapper(Fraction(2, 1)) <= 5

    # _place_note out-of-bounds and ghost branches.
    row_grid = [["-"] * 4 for _ in range(1)]
    renderer._place_note(
        row_grid,
        3,
        0,
        NoteEvent(
            start=Fraction(0, 1), duration=Fraction(1, 1), string_index=0, fret=2
        ),
    )
    renderer._place_note(
        row_grid,
        0,
        10,
        NoteEvent(
            start=Fraction(0, 1), duration=Fraction(1, 1), string_index=0, fret=2
        ),
    )
    renderer._place_note(
        row_grid,
        0,
        0,
        NoteEvent(
            start=Fraction(0, 1),
            duration=Fraction(1, 1),
            string_index=0,
            fret=4,
            is_ghost=True,
        ),
    )
    assert row_grid[0][0] == "("

    # _place_token clamps to row bounds.
    row = list("----")
    renderer._place_token(row, 3, "XYZ")
    assert "".join(row) == "---X"

    assert renderer._bar_token(Barline.DOUBLE_ENDING) == "*|"
    assert renderer._infer_measure_width(_make_measure([], width=None)) == 16
    many_events = _make_measure(
        [RestEvent(start=Fraction(i, 1), duration=Fraction(1, 1)) for i in range(40)],
        width=None,
    )
    assert renderer._infer_measure_width(many_events) == 96

    assert renderer._duration_symbol_for(Fraction(4, 1)) == "W"
    assert renderer._duration_symbol_for(Fraction(2, 1)) == "H"
    assert renderer._duration_symbol_for(Fraction(1, 8)) == "T"
    assert renderer._duration_symbol_for(Fraction(1, 16)) == "X"
    assert renderer._duration_symbol_for(Fraction(99, 1)) == "Q"
