from __future__ import annotations

from fractions import Fraction
import textwrap

import pytest

from tabulator_parser import parse_tab, validate_score
from tabulator_parser.tab_model import Barline, ChordEvent, NoteEvent, RestEvent
from tabulator_parser.tab_parser import TabParseError


def _with_header(body: str) -> str:
    return f"title: Test Song\nartist: Test Artist\n\n{textwrap.dedent(body).strip()}\n"


def test_parse_tab_requires_mandatory_header_fields():
    with pytest.raises(TabParseError):
        parse_tab("title: Missing Artist\n\nE|0|\n")

    with pytest.raises(TabParseError):
        parse_tab("artist: Missing Title\n\nE|0|\n")


def test_parser_populates_model_for_unknown_rhythm_with_warnings_and_pitches():
    text = _with_header("""
        %%%%
        E|0-(2)-x-|
        B|--3-----|
        G|--------|
        D|--------|
        A|--------|
        E|--------|
        """)
    score = parse_tab(text)

    warnings = validate_score(score)
    assert len(warnings) == 1
    assert "Unrecognized line skipped" in warnings[0].message

    # validate_score returns a copy
    warnings.append(warnings[0])
    assert len(validate_score(score)) == 1

    system = score.sections[0].systems[0]
    assert system.tuning.labels == ["E", "B", "G", "D", "A", "E"]
    measure = system.measures[0]

    note_events = [ev for ev in measure.events if isinstance(ev, NoteEvent)]
    assert any(ev.is_ghost for ev in note_events)
    assert any(ev.fret is None for ev in note_events)
    assert any(ev.pitch is not None for ev in note_events)
    assert all(isinstance(ev.start, Fraction) for ev in note_events)


def test_parser_reads_capo_from_header():
    text = _with_header("""
        capo: 7
        E|0|
        B|0|
        """)
    score = parse_tab(text)
    assert score.capo == 7


def test_parser_populates_duration_mode_events_annotations_tuplets_and_timesig():
    text = _with_header("""
        3/4
        PM---|
        |-3-|
         +QaEqWx2
        E|0-2x-5--|
        B|1-------|
        """)
    score = parse_tab(text)

    section = score.sections[0]
    assert str(section.time_signature) == "3/4"

    system = section.systems[0]
    assert len(system.annotations) >= 1
    assert len(system.tuplets) >= 1
    assert system.duration_line is not None

    measure = system.measures[0]
    assert measure.barline_left == Barline.SINGLE
    assert measure.barline_right == Barline.SINGLE
    assert len(measure.events) == 5

    chords = [ev for ev in measure.events if isinstance(ev, ChordEvent)]
    notes = [ev for ev in measure.events if isinstance(ev, NoteEvent)]
    rests = [ev for ev in measure.events if isinstance(ev, RestEvent)]

    assert len(chords) == 1
    assert len(chords[0].notes) == 2
    assert any(n.tie is not None and n.tie.continued for n in chords[0].notes)
    assert any(n.grace for n in notes)
    assert any(n.fret is None and n.pitch is None for n in notes)
    assert any(ev.duration == Fraction(1, 2) for ev in rests)
    assert any(ev.duration == Fraction(6, 1) for ev in measure.events)


def test_parser_sections_timestamps_repeat_barlines_and_inconsistent_warning():
    text = _with_header("""
        1:07
        6/4
        D||o0--o||
        A||o0--o||

        1:21
        D|0--|0-|
        A|0---|0|
        """)
    score = parse_tab(text)

    assert len(score.sections) == 2
    assert score.sections[0].timestamp == "1:07"
    assert str(score.sections[0].time_signature) == "6/4"
    assert score.sections[1].timestamp == "1:21"

    m0 = score.sections[0].systems[0].measures[0]
    assert m0.barline_left == Barline.REPEAT_START
    assert m0.barline_right == Barline.REPEAT_END

    warnings = validate_score(score)
    assert any("Inconsistent barline positions" in w.message for w in warnings)
