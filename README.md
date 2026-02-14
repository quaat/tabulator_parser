# ASCII Guitar Tab → Structured Model → MIDI

This project provides:

-   `tab_parser.py` --- Parses extended ASCII guitar tab into a
    structured `TabDocument` with rhythm resolution.
-   `tab_to_midi.py` --- Converts a `TabDocument` into a multi-track
    MIDI file using `mido`.

The system is designed for rich transcription formats, including:

-   Multiple guitars (Gtr I, Gtr II, etc.)
-   Explicit tuning per track
-   Tempo changes (`Q=190`, `E=120`, etc.)
-   Time signatures (`6/4`, `12/8`, etc.)
-   Timestamp anchors (`1:07`, `4:55`, etc.)
-   Duration lines aligned above tab staff
-   Guitar techniques (hammer-ons, bends, slides, etc.)

------------------------------------------------------------------------

# Requirements

## Python

-   Python 3.10+ recommended

## Dependencies

### Required

    pip install mido

### Optional (for realtime MIDI output)

    pip install python-rtmidi

No external parsing libraries are required for the tab format itself.

------------------------------------------------------------------------

# Text Tabulator Notation Requirements

The parser expects a structured ASCII tab format similar to professional
transcription layouts.

------------------------------------------------------------------------

## 1. Metadata Section (Optional but Recommended)

Example:

    Ghost Of Perdition Tab by Opeth
    Difficulty: advanced
    Tuning: D A D F# A D

Supported fields:

-   `Tuning:` (space-separated note names)
-   `Difficulty:`
-   Free-form title/artist lines

If no tuning is defined at track-level, global `Tuning:` is used as
fallback.

------------------------------------------------------------------------

## 2. Track Declarations

Example:

    Gtr I (D A D F A D) - 'Clean'
    Gtr II (D A D F A D) - 'Dist Center'

Format:\
`Gtr <Roman|Number> (<tuning>) - '<role>'`

Each track becomes: - A separate MIDI track - Assigned a General MIDI
guitar program based on role

------------------------------------------------------------------------

## 3. Timestamp Anchors

Segments may begin with timestamps:

    0:00
    1:07
    4:55

These anchor the segment to absolute time (seconds) in the final MIDI
file.

------------------------------------------------------------------------

## 4. Tempo Markers

Format:

    Q=190
    E=120

Meaning: - Letter = rhythmic unit - Number = BPM

If no tempo is defined: default = `Q=120`

------------------------------------------------------------------------

## 5. Time Signatures

Format:

    6/4
    12/8
    4/4

Used for: - Beat resolution - MIDI time_signature meta events

------------------------------------------------------------------------

## 6. Duration Lines (Required for Rhythm Resolution)

Durations must appear directly above tab lines and align vertically with
fret numbers.

Example:

       Q   E E E E   H.
    D|-------------------|
    A|--5---5-5-5-5------|

Supported symbols:

  Symbol      Meaning
  ----------- ----------
  W           Whole
  H           Half
  Q           Quarter
  E           8th
  S           16th
  T           32nd
  X           64th
  \+          Tie
  .           Dotted
  lowercase   Staccato

Rules: - Duration letters must align with fret positions - If no fret
appears under a duration → rest - `+` ties to previous duration - Dotted
durations supported (`Q.`, `H..`)

If duration lines are missing: - Events default to quarter note timing

------------------------------------------------------------------------

## 7. Staff Format

Standard 6-line ASCII staff:

    D|----------------|
    A|----------------|
    F|----------------|
    D|----------------|
    A|----------------|
    D|----------------|

Rules: - Each system must contain consistent 6-line blocks - Lines must
begin with note letter + `|` - Columns must align across strings

------------------------------------------------------------------------

## 8. Techniques

Parsed tokens include:

-   `h` hammer-on
-   `p` pull-off
-   `b` bend
-   `r` release
-   `s` slide
-   `/` slide up
-   `\` slide down
-   `~` vibrato
-   `PM` palm mute
-   `TP` tremolo picking

Current MIDI rendering: - Multi-fret tokens split evenly across
duration - Techniques not yet mapped to pitch bend or CC

------------------------------------------------------------------------

# Usage Examples

## Parse a Tab

``` python
from tab_parser import parse_tab

with open("song.txt") as f:
    text = f.read()

doc = parse_tab(text)
print(doc.metadata.title)
```

## Convert to MIDI

``` python
from tab_parser import parse_tab
from tab_to_midi import tabdocument_to_midi

doc = parse_tab(open("song.txt").read())
tabdocument_to_midi(doc, "output.mid")
```

## Command Line

    python tab_to_midi.py song.txt output.mid

Optional:

    python tab_to_midi.py song.txt output.mid --ticks 960 --velocity 90

------------------------------------------------------------------------

# MIDI Output Details

-   Conductor track (tempo + time signatures)
-   One MIDI track per guitar track id
-   Timing derived from:
    -   Duration lines
    -   Tempo markers
    -   Timestamp anchors

Default PPQ: 480

------------------------------------------------------------------------

# Known Limitations

-   Tuplets not explicitly supported
-   Repeat markers not expanded
-   Advanced expressive techniques not mapped to MIDI CC
-   Overlapping tempo changes assumed monotonic

------------------------------------------------------------------------

# Summary

This system converts structured ASCII guitar tablature into a
deterministic, tempo-accurate MIDI representation suitable for analysis,
reconstruction, or digital playback.