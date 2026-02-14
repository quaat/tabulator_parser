from __future__ import annotations

import tabulator_parser as tp


def test_public_api_exports_are_available():
    expected_names = {
        "parse_tab",
        "validate_score",
        "render_tab",
        "render_tab_from_model",
        "to_midi_events",
        "TabScore",
        "TabSystem",
        "Section",
        "Measure",
        "TimeSignature",
        "Barline",
        "NoteEvent",
        "ChordEvent",
        "RestEvent",
        "DurationToken",
        "MidiEvent",
        "TabParseError",
    }

    assert expected_names.issubset(set(tp.__all__))

    # Import style required by caller packages.
    from tabulator_parser import TabScore, parse_tab, render_tab, to_midi_events

    assert parse_tab is tp.parse_tab
    assert render_tab is tp.render_tab
    assert to_midi_events is tp.to_midi_events
    assert TabScore is tp.TabScore
