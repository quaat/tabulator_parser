from __future__ import annotations

from dataclasses import FrozenInstanceError
from fractions import Fraction

import pytest

from tabulator_parser.tab_model import (
    AnnotationSpan,
    Barline,
    ChordEvent,
    DurationToken,
    HammerOn,
    Measure,
    MidiEvent,
    Muted,
    NoteEvent,
    ParseWarning,
    PullOff,
    RestEvent,
    Section,
    SlideIn,
    TabScore,
    TabSystem,
    TieInfo,
    TimeSignature,
    Tuning,
    TupletSpan,
    UnknownTechnique,
    Vibrato,
)


def test_timesignature_and_enum_values():
    ts = TimeSignature(6, 8)
    assert str(ts) == "6/8"
    assert Barline.SINGLE.value == "|"
    assert Barline.DOUBLE.value == "||"
    assert Barline.REPEAT_START.value == "||o"
    assert Barline.REPEAT_END.value == "o||"
    assert Barline.DOUBLE_ENDING.value == "*|"


def test_frozen_model_objects_are_immutable():
    ts = TimeSignature(4, 4)
    warn = ParseWarning(3, "warn")
    span = TupletSpan(3, 2, 10, 15)
    ann = AnnotationSpan("PM", 1, 5)
    dur = DurationToken(raw="+Q.", symbol="Q", dotted=1, tie=True)
    tie = TieInfo()
    tech = UnknownTechnique("??")

    with pytest.raises(FrozenInstanceError):
        ts.numerator = 5  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        warn.line_no = 10  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        span.actual = 5  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        ann.type = "X"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        dur.raw = "Q"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        tie.continued = False  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        tech.raw = "ok"  # type: ignore[misc]


def test_event_and_container_defaults():
    note = NoteEvent(
        start=Fraction(0, 1), duration=Fraction(1, 2), string_index=0, fret=3
    )
    chord = ChordEvent(start=Fraction(0, 1), duration=Fraction(1, 2), notes=[note])
    rest = RestEvent(start=Fraction(1, 2), duration=Fraction(1, 2))
    measure = Measure(
        barline_left=Barline.SINGLE,
        barline_right=Barline.DOUBLE,
        time_signature=TimeSignature(4, 4),
        events=[note, chord, rest],
        raw_columns=16,
    )
    system = TabSystem(tuning=Tuning(labels=["E", "B", "G"]), measures=[measure])
    section = Section(
        timestamp="0:42", time_signature=TimeSignature(4, 4), systems=[system]
    )
    score = TabScore(title="Song", artist="Artist", capo=1, sections=[section])
    midi = MidiEvent(time_sec=0.0, type="note_on", pitch=64)

    assert score.sections[0].systems[0].measures[0].events[1].notes[0].fret == 3
    assert note.notations == []
    assert note.techniques == []
    assert note.tie is None
    assert note.grace is False
    assert note.pitch is None
    assert note.is_ghost is False
    assert chord.notes[0] is note
    assert midi.velocity == 90
    assert midi.channel == 0


def test_technique_dataclasses_construct():
    h = HammerOn(from_fret=1, to_fret=3)
    p = PullOff(from_fret=3, to_fret=1)
    s = SlideIn(direction="/")
    m = Muted()
    v = Vibrato()

    assert (h.from_fret, h.to_fret) == (1, 3)
    assert (p.from_fret, p.to_fret) == (3, 1)
    assert s.direction == "/"
    assert isinstance(m, Muted)
    assert isinstance(v, Vibrato)
