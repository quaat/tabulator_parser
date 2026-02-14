# tabulator-parser

Parse ASCII guitar tablature into a structured Python model, render it back to tab text, and convert notes into timestamped MIDI-style note events.

## Features

- Parse tab text into a typed model (`TabScore`, `Section`, `TabSystem`, `Measure`, events).
- Support both:
  - Duration-driven rhythm parsing (using duration annotation lines).
  - Fallback column-based parsing when no duration line is present.
- Parse common tab techniques and note forms:
  - `h` hammer-on, `p` pull-off, `/` and `\` slide-in, `~` vibrato.
  - muted notes `x`, ghost notes `(n)`.
- Parse system-level annotations:
  - palm-mute spans (`PM...|` style lines),
  - triplet markers (`|-3-|` style lines).
- Render with two strategies:
  - `render_tab`: conservative round-trip renderer using captured raw system lines.
  - `render_tab_from_model`: model-driven renderer.
- Convert parsed notes/chords into ordered `MidiEvent` note_on/note_off events (`to_midi_events`).
- Pip-installable package API:
  - `from tabulator_parser import ...`

## Requirements

- Python `>=3.12`
- Runtime dependency: `mido`

## Installation

```bash
pip install tabulator-parser
```

For development:

```bash
pip install -e ".[dev]"
```

## Quick Start

```python
from tabulator_parser import parse_tab, validate_score, render_tab, to_midi_events

text = """\
title: Example Song
artist: Example Artist
capo: 2

1:07
6/4
   Q  E E Q
D|--0--2--3--|
A|-----------|
"""

score = parse_tab(text)
warnings = validate_score(score)
round_trip_text = render_tab(score)
midi_events = to_midi_events(score, tempo_bpm=120.0)
```

## Tabulator Annotation Reference

This section documents the tab format accepted by the parser.

### 1) Header (required)

The first block must contain:

- `title: <text>` (required)
- `artist: <text>` (required)
- `capo: <int>` (optional)

If `title` or `artist` is missing, parsing raises `TabParseError`.

### 2) Section markers

You can declare section context lines before systems:

- Timestamp: `m:ss` (example: `1:21`)
- Time signature: `N/D` (example: `6/4`, `12/8`)

Timestamp starts a new section. Time signature is carried forward until changed.

### 3) System structure

A system is parsed from:

- optional pre-lines (duration/annotation lines),
- followed by one or more string lines.

String lines may be:

- labeled: `E|...`, `D|...`, `F#|...`, `Bb|...`
- unlabeled: `|...`

For unlabeled 6-string systems, tuning defaults to `["E","B","G","D","A","E"]`.

### 4) Barlines

Recognized bar tokens:

- `|`
- `||`
- `||o` (repeat start)
- `o||` (repeat end)
- `*|` (double ending marker)

Measures are segmented from barline positions.

### 5) Duration annotation line

When a duration line is present, rhythm is parsed from duration tokens aligned by column.

Supported duration symbols:

- `W` whole, `H` half, `Q` quarter, `E` eighth, `S` sixteenth, `T` thirty-second, `X` sixty-fourth
- lowercase versions are treated as staccato (duration halved)
- `.` / `..` dotted / double-dotted
- `+` tie flag on the token (example `+Q`, `+H.`)
- `a` grace token (zero duration)
- `WxN` multibar rest shorthand (example `Wx2`)

If no note is found under a parsed duration token, a `RestEvent` is created.

If no duration line is present, parser falls back to column-based timing.

### 6) Note and technique tokens

Per-string note parsing supports:

- frets: `0`, `3`, `10`, ...
- ghost notes: `(3)`
- muted note: `x`
- slide-in: `/7` or `\7`
- inline legato: `1h3`, `4p2`
- immediate vibrato marker: `9~`

### 7) System annotations

Recognized annotation lines:

- Palm mute span: patterns containing `PM...|`
- Triplet marker: `|-3-|` (supports ASCII and common Unicode dash variants)

These are stored as:

- `AnnotationSpan(type="PM", start_col, end_col)`
- `TupletSpan(actual=3, normal=2, start_col, end_col)`

### 8) Warnings and validation

Parsing is best-effort. Non-fatal issues are collected as `ParseWarning` in `score.metadata["warnings"]`.

Use:

```python
from tabulator_parser import validate_score
warnings = validate_score(score)
```

Examples of warnings:

- unrecognized skipped lines
- inconsistent barline positions across strings

## Public API

Primary imports:

```python
from tabulator_parser import (
    parse_tab,
    validate_score,
    render_tab,
    render_tab_from_model,
    to_midi_events,
    TabScore,
    Section,
    TabSystem,
    Measure,
    NoteEvent,
    ChordEvent,
    RestEvent,
)
```

## Current Limitations

- Parser targets a single score model, not multi-track guitar arrangements.
- Tempo markers like `Q=190` are not currently parsed; `to_midi_events` uses provided `tempo_bpm`.
- Tuplet markers are captured as spans but do not currently rescale durations.
- Technique coverage is intentionally limited to currently implemented tokens.
- MIDI export currently returns note events (`MidiEvent`) rather than writing `.mid` files.
