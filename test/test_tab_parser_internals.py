from __future__ import annotations

from fractions import Fraction

import pytest

import tabulator_parser.tab_parser as parser
from tabulator_parser.tab_model import (
    Barline,
    ChordEvent,
    DurationToken,
    Measure,
    NoteEvent,
    TimeSignature,
    Tuning,
)
from tabulator_parser.tab_parser import TabParseError


def test_collect_system_block_and_count_string_lines():
    lines = [
        "   Q E",
        "E|0--|",
        "B|1--|",
        "",
        "1:23",
        "X not a system line",
    ]
    block, consumed = parser._collect_system_block(lines, 0)
    assert consumed == 3
    assert parser._count_string_lines(block) == 2

    empty_block, empty_consumed = parser._collect_system_block(lines, 3)
    assert empty_block == []
    assert empty_consumed == 0

    ts_block, ts_consumed = parser._collect_system_block(lines, 4)
    assert ts_block == []
    assert ts_consumed == 0

    bad_block, bad_consumed = parser._collect_system_block(lines, 5)
    assert bad_block == []
    assert bad_consumed == 0

    # Unknown line before any strings -> early reject branch.
    pre_bad, pre_bad_consumed = parser._collect_system_block(["%%%%", "E|0|"], 0)
    assert pre_bad == []
    assert pre_bad_consumed == 0

    # Interleaved annotation after strings and break on timestamp.
    mixed_lines = ["E|0--|", "PM---|", "1:23", "B|1--|"]
    mixed_block, mixed_consumed = parser._collect_system_block(mixed_lines, 0)
    assert mixed_consumed == 2
    assert parser._count_string_lines(mixed_block) == 1

    # Break on header line after strings.
    header_break, header_consumed = parser._collect_system_block(
        ["E|0--|", "title: stop"], 0
    )
    assert header_consumed == 1
    assert parser._count_string_lines(header_break) == 1

    # Break on unknown line after strings.
    unknown_break, unknown_consumed = parser._collect_system_block(
        ["E|0--|", "%%%%"], 0
    )
    assert unknown_consumed == 1
    assert parser._count_string_lines(unknown_break) == 1


def test_line_classifiers_and_barline_helpers():
    assert parser._is_string_line("E|---0---|")
    assert parser._is_string_line("|---0---|")
    assert not parser._is_string_line("|-3-|")
    assert not parser._is_string_line("PM---|")

    assert parser._is_annotation_or_duration("6/8")
    assert parser._is_annotation_or_duration("1:23")
    assert parser._is_annotation_or_duration("PM----|")
    assert parser._is_annotation_or_duration("|-3-|")
    assert parser._is_annotation_or_duration("  Q E S")
    assert parser._is_annotation_or_duration("  Q|E|S")
    assert not parser._is_annotation_or_duration("zzzz")

    tokens = list(parser._find_bar_tokens("||o x o|| y || z *| w |"))
    assert [tok for _, _, tok in tokens] == ["||o", "o||", "||", "*|", "|"]

    assert parser._barline_from_token("||o") == Barline.REPEAT_START
    assert parser._barline_from_token("o||") == Barline.REPEAT_END
    assert parser._barline_from_token("||") == Barline.DOUBLE
    assert parser._barline_from_token("*|") == Barline.DOUBLE_ENDING
    assert parser._barline_from_token("|") == Barline.SINGLE


def test_parse_system_block_without_string_lines_raises():
    with pytest.raises(TabParseError):
        parser._parse_system_block(
            [(1, "Q E E"), (2, "PM--|")], base_line=1, effective_ts=TimeSignature(4, 4)
        )


def test_parse_system_block_unlabeled_defaults_and_synthetic_bars():
    unlabeled = [
        (1, "|0----"),
        (2, "|-----"),
        (3, "|-----"),
        (4, "|-----"),
        (5, "|-----"),
        (6, "|-----"),
    ]
    system, warnings = parser._parse_system_block(
        unlabeled, base_line=1, effective_ts=TimeSignature(4, 4)
    )
    assert len(warnings) == 5
    assert system.tuning.labels == ["E", "B", "G", "D", "A", "E"]
    assert len(system.measures) == 1


def test_duration_token_parsing_and_conversion_helpers():
    assert parser._maybe_parse_duration_at("Q", 2) is None
    assert parser._maybe_parse_duration_at("+", 0) is None
    assert parser._maybe_parse_duration_at("?", 0) is None

    tok, consumed = parser._maybe_parse_duration_at("+E..", 0)
    assert tok.raw == "+E.."
    assert tok.tie is True
    assert tok.dotted == 2
    assert consumed == 4

    tok2, consumed2 = parser._maybe_parse_duration_at("Wx3", 0)
    assert tok2.multibar_rests == 3
    assert consumed2 == 3

    parsed = parser._parse_duration_token("+wx2")
    assert parsed.tie is True
    assert parsed.staccato is True
    assert parsed.multibar_rests == 2

    tok_dot1 = DurationToken(raw="Q.", symbol="Q", dotted=1)
    _, dur1 = parser._duration_token_to_beats(tok_dot1, TimeSignature(4, 4))
    assert dur1 == Fraction(3, 2)

    tok_dot2 = DurationToken(raw="Q..", symbol="Q", dotted=2)
    _, dur2 = parser._duration_token_to_beats(tok_dot2, TimeSignature(4, 4))
    assert dur2 == Fraction(7, 4)

    tok_stac = DurationToken(raw="q", symbol="q", staccato=True)
    _, dur3 = parser._duration_token_to_beats(tok_stac, TimeSignature(4, 4))
    assert dur3 == Fraction(1, 2)

    tok_multi = DurationToken(raw="Wx2", symbol="W", multibar_rests=2)
    _, dur4 = parser._duration_token_to_beats(tok_multi, TimeSignature(3, 4))
    assert dur4 == Fraction(6, 1)

    raw_ok = parser._maybe_parse_duration_at_raw("+W..x2", 0)
    assert raw_ok == ("+W..", 4)
    assert parser._maybe_parse_duration_at_raw("Q", 1) is None
    assert parser._maybe_parse_duration_at_raw("Wx2", 0) == ("Wx2", 3)
    assert parser._maybe_parse_duration_at_raw("+", 0) is None
    assert parser._maybe_parse_duration_at_raw("?", 0) is None


def test_note_parsing_and_pitch_assignment_helpers():
    # out of bounds
    assert parser._parse_note_at("123", 10) == (None, [], 0)

    # slide-in
    note, techniques, consumed = parser._parse_note_at("/12", 0)
    assert note["fret"] == 12
    assert techniques[0].direction == "/"
    assert consumed == 3

    # backslash slide-in
    note, techniques, consumed = parser._parse_note_at("\\7", 0)
    assert note["fret"] == 7
    assert techniques[0].direction == "\\"
    assert consumed == 2

    # hammer-on
    note, techniques, consumed = parser._parse_note_at("1h3", 0)
    assert note["fret"] == 3
    assert techniques and techniques[0].__class__.__name__ == "HammerOn"
    assert consumed == 3

    # pull-off
    note, techniques, consumed = parser._parse_note_at("4p2", 0)
    assert note["fret"] == 2
    assert techniques and techniques[0].__class__.__name__ == "PullOff"
    assert consumed == 3

    # vibrato
    note, techniques, consumed = parser._parse_note_at("9~", 0)
    assert note["fret"] == 9
    assert techniques and techniques[0].__class__.__name__ == "Vibrato"
    assert consumed == 1

    # ghost note
    note, techniques, consumed = parser._parse_note_at("(7)", 0)
    assert note["fret"] == 7
    assert note["ghost"] is True
    assert techniques == []
    assert consumed == 3

    # muted
    note, techniques, consumed = parser._parse_note_at("x", 0)
    assert note["fret"] is None
    assert techniques and techniques[0].__class__.__name__ == "Muted"
    assert consumed == 1

    # non-note
    assert parser._parse_note_at("-", 0) == (None, [], 0)

    measure = Measure(
        barline_left=Barline.SINGLE,
        barline_right=Barline.SINGLE,
        time_signature=TimeSignature(4, 4),
        events=[
            NoteEvent(
                start=Fraction(0, 1), duration=Fraction(1, 1), string_index=0, fret=2
            ),
            NoteEvent(
                start=Fraction(0, 1), duration=Fraction(1, 1), string_index=99, fret=2
            ),
            ChordEvent(
                start=Fraction(0, 1),
                duration=Fraction(1, 1),
                notes=[
                    NoteEvent(
                        start=Fraction(0, 1),
                        duration=Fraction(1, 1),
                        string_index=1,
                        fret=3,
                    ),
                    NoteEvent(
                        start=Fraction(0, 1),
                        duration=Fraction(1, 1),
                        string_index=1,
                        fret=None,
                    ),
                ],
            ),
        ],
    )
    parser._assign_pitches(measure, Tuning(labels=["E", "B"]))
    assert measure.events[0].pitch == 66
    assert measure.events[1].pitch is None
    chord = measure.events[2]
    assert isinstance(chord, ChordEvent)
    assert chord.notes[0].pitch == 74
    assert chord.notes[1].pitch is None

    midi = parser._tuning_to_open_midi(["E", "Bb", "Q", "G#", "Db", "A"])
    assert midi[0] == 64
    assert midi[1] == 58
    assert midi[2] == 52  # fallback for unknown label at this string octave
    assert len(parser._tuning_to_open_midi(["E", "A", "D"])) == 3


def test_parse_measure_events_paths_for_unknown_and_duration_modes():
    # Unknown rhythm mode
    m_unknown = Measure(
        barline_left=Barline.SINGLE,
        barline_right=Barline.SINGLE,
        time_signature=TimeSignature(4, 4),
        events=[],
    )
    parser._parse_measure_events(
        measure=m_unknown,
        string_slices=["0-(2)-x-"],
        dur_slice=None,
        tuning=Tuning(labels=["E"]),
        warnings=[],
        base_line=1,
        col_offset=0,
    )
    assert any(isinstance(ev, NoteEvent) for ev in m_unknown.events)
    assert any(isinstance(ev, NoteEvent) and ev.fret is None for ev in m_unknown.events)

    # Duration-driven mode with no note at one duration token -> RestEvent branch.
    m_dur = Measure(
        barline_left=Barline.SINGLE,
        barline_right=Barline.SINGLE,
        time_signature=TimeSignature(4, 4),
        events=[],
    )
    parser._parse_measure_events(
        measure=m_dur,
        string_slices=["0---"],
        dur_slice="QQQQ",
        tuning=Tuning(labels=["E"]),
        warnings=[],
        base_line=1,
        col_offset=0,
    )
    assert len(m_dur.events) == 4
    assert any(ev.__class__.__name__ == "RestEvent" for ev in m_dur.events)
