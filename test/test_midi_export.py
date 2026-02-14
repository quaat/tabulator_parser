from __future__ import annotations

from fractions import Fraction

from tabulator_parser.midi_export import to_midi_events
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


def test_to_midi_events_handles_note_chord_rest_and_pitchless_events():
    m1_events = [
        RestEvent(start=Fraction(0, 1), duration=Fraction(1, 1)),
        NoteEvent(
            start=Fraction(0, 1),
            duration=Fraction(1, 1),
            string_index=0,
            fret=0,
            pitch=64,
        ),
        NoteEvent(
            start=Fraction(1, 1),
            duration=Fraction(1, 1),
            string_index=0,
            fret=0,
            pitch=None,
        ),
        ChordEvent(
            start=Fraction(2, 1),
            duration=Fraction(1, 2),
            notes=[
                NoteEvent(
                    start=Fraction(2, 1),
                    duration=Fraction(1, 2),
                    string_index=0,
                    fret=3,
                    pitch=67,
                ),
                NoteEvent(
                    start=Fraction(2, 1),
                    duration=Fraction(1, 2),
                    string_index=1,
                    fret=2,
                    pitch=61,
                ),
                NoteEvent(
                    start=Fraction(2, 1),
                    duration=Fraction(1, 2),
                    string_index=2,
                    fret=2,
                    pitch=None,
                ),
            ],
        ),
    ]
    m1 = Measure(
        barline_left=Barline.SINGLE,
        barline_right=Barline.SINGLE,
        time_signature=TimeSignature(4, 4),
        events=m1_events,
    )
    # Zero-duration measure (no time advance) to hit branch.
    m2 = Measure(
        barline_left=Barline.SINGLE,
        barline_right=Barline.SINGLE,
        time_signature=TimeSignature(4, 4),
        events=[],
    )
    system = TabSystem(tuning=Tuning(labels=["E", "B", "G"]), measures=[m1, m2])
    score = TabScore(
        title="T", artist="A", capo=None, sections=[Section(systems=[system])]
    )

    events = to_midi_events(score, tempo_bpm=120.0)

    # Expected pitched events: 1 single note => 2 events, 2 chord notes => 4 events.
    assert len(events) == 6
    assert all(e.pitch in (64, 67, 61) for e in events)
    assert events[0].type == "note_on"
    assert events[-1].type == "note_off"

    # 120 BPM => 0.5 sec per beat.
    times = [e.time_sec for e in events]
    assert min(times) == 0.0
    assert max(times) == 1.25
