from __future__ import annotations

from fractions import Fraction

from .tab_model import ChordEvent, MidiEvent, NoteEvent, RestEvent, TabScore


def to_midi_events(score: TabScore, tempo_bpm: float = 120.0) -> list[MidiEvent]:
    """
    Returns events with absolute time in seconds.

    Timing basis:
    - Event.start and Event.duration are in quarter-note beats (Fraction).
    - seconds_per_beat = 60 / tempo_bpm
    """
    sec_per_beat = 60.0 / float(tempo_bpm)
    events: list[MidiEvent] = []
    t_abs_beats = Fraction(0, 1)

    for section in score.sections:
        for system in section.systems:
            for measure in system.measures:
                # measure.events are relative to measure; convert to absolute by adding t_abs_beats
                for ev in measure.events:
                    if isinstance(ev, RestEvent):
                        continue
                    if isinstance(ev, NoteEvent):
                        if ev.pitch is None:
                            continue
                        t_on = float(t_abs_beats + ev.start) * sec_per_beat
                        t_off = (
                            float(t_abs_beats + ev.start + ev.duration) * sec_per_beat
                        )
                        events.append(
                            MidiEvent(time_sec=t_on, type="note_on", pitch=ev.pitch)
                        )
                        events.append(
                            MidiEvent(time_sec=t_off, type="note_off", pitch=ev.pitch)
                        )
                    elif isinstance(ev, ChordEvent):
                        for ne in ev.notes:
                            if ne.pitch is None:
                                continue
                            t_on = float(t_abs_beats + ne.start) * sec_per_beat
                            t_off = (
                                float(t_abs_beats + ne.start + ne.duration)
                                * sec_per_beat
                            )
                            events.append(
                                MidiEvent(time_sec=t_on, type="note_on", pitch=ne.pitch)
                            )
                            events.append(
                                MidiEvent(
                                    time_sec=t_off, type="note_off", pitch=ne.pitch
                                )
                            )

                # advance absolute time by measure length if we can infer it
                # best-effort: sum of durations in the measure for duration-driven parses
                total = sum((ev.duration for ev in measure.events), Fraction(0, 1))
                if total > 0:
                    t_abs_beats += total

    # Sort by time, note_off after note_on when same time
    events.sort(key=lambda e: (e.time_sec, 0 if e.type == "note_on" else 1, e.pitch))
    return events
