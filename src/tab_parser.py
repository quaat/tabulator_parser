from __future__ import annotations

import re
from fractions import Fraction
from typing import Iterable, Optional, Tuple

from .tab_model import (
    AnnotationSpan,
    Barline,
    ChordEvent,
    DurationToken,
    HammerOn,
    Muted,
    NoteEvent,
    ParseWarning,
    PullOff,
    RestEvent,
    Section,
    SlideIn,
    TabScore,
    TabSystem,
    Technique,
    TimeSignature,
    Tuning,
    TupletSpan,
    Vibrato,
    TieInfo,
    Measure,
)

DURATION_SYMBOLS = set(list("WHQESTXa") + list("whqestx"))  # include lowercase forms


class TabParseError(ValueError):
    pass


def parse_tab(text: str) -> TabScore:
    lines = text.splitlines()
    score, idx = _parse_header(lines)
    sections, warnings = _parse_sections(lines[idx:])
    score.sections = sections
    score.metadata["warnings"] = warnings
    return score


def validate_score(score: TabScore) -> list[ParseWarning]:
    return list(score.metadata.get("warnings", []))


# ---------------- Header ----------------


def _parse_header(lines: list[str]) -> Tuple[TabScore, int]:
    title = artist = None
    capo: Optional[int] = None
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        m = re.match(r"^title:\s*(.+)$", line, re.IGNORECASE)
        if m:
            title = m.group(1).strip()
            i += 1
            continue
        m = re.match(r"^artist:\s*(.+)$", line, re.IGNORECASE)
        if m:
            artist = m.group(1).strip()
            i += 1
            continue
        m = re.match(r"^capo:\s*(\d+)\s*$", line, re.IGNORECASE)
        if m:
            capo = int(m.group(1))
            i += 1
            continue
        break  # end of header block
    if not title or not artist:
        raise TabParseError(
            "Missing mandatory header fields: 'title:' and/or 'artist:'."
        )
    return TabScore(title=title, artist=artist, capo=capo, sections=[]), i


# ---------------- Sections / Systems ----------------

_TS_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")
_TIMESTAMP_RE = re.compile(r"^\s*(\d+):(\d{2})\s*$")
_STRING_LABELED_RE = re.compile(r"^\s*([A-Ga-g])([#b])?\s*\|")
_STRING_UNLABELED_RE = re.compile(r"^\s*\|")
# _TRIPLET_RE = re.compile(r"\|\s*[-–—]+\s*3\s*[-–—]+\s*\|")
_TRIPLET_RE = re.compile(r"[|│]\s*[-–—-−]+\s*3\s*[-–—-−]+\s*[|│]")
_PM_RE = re.compile(r"PM[-\s]*\|")


def _parse_sections(lines: list[str]) -> Tuple[list[Section], list[ParseWarning]]:
    i = 0
    warnings: list[ParseWarning] = []
    sections: list[Section] = []
    current_ts = TimeSignature(4, 4)
    current_section = Section(timestamp=None, time_signature=None, systems=[])

    def flush_section():
        nonlocal current_section
        if current_section.systems:
            sections.append(current_section)
        current_section = Section(timestamp=None, time_signature=None, systems=[])

    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            i += 1
            continue

        # Timestamp line applies to following section/system group
        m = _TIMESTAMP_RE.match(raw)
        if m:
            flush_section()
            mm = int(m.group(1))
            ss = int(m.group(2))
            current_section.timestamp = f"{mm}:{ss:02d}"
            i += 1
            continue

        # Time signature line persists
        m = _TS_RE.match(raw)
        if m:
            current_ts = TimeSignature(int(m.group(1)), int(m.group(2)))
            if current_section.time_signature is None:
                current_section.time_signature = current_ts
            i += 1
            continue

        # Try to parse a system starting at i
        sys_lines, consumed = _collect_system_block(lines, i)
        if consumed == 0:
            # Unrecognized line; skip but warn
            warnings.append(
                ParseWarning(
                    line_no=i + 1, message=f"Unrecognized line skipped: {raw!r}"
                )
            )
            i += 1
            continue

        system, sys_warnings = _parse_system_block(
            sys_lines, base_line=i + 1, effective_ts=current_ts
        )
        warnings.extend(sys_warnings)
        current_section.systems.append(system)
        i += consumed

    flush_section()
    return sections, warnings


def _collect_system_block(
    lines: list[str], start: int
) -> Tuple[list[Tuple[int, str]], int]:
    """
    Returns list of (line_no, line_text) for a system-ish block, and number consumed.
    A system block may begin with annotation lines (duration, PM, triplet, time sig),
    followed by N string lines. We must keep those pre-lines with the strings.
    """
    block: list[Tuple[int, str]] = []
    i = start

    # 1) Collect leading annotation/duration lines (but stop on timestamp or blank)
    while i < len(lines):
        s = lines[i]
        if not s.strip():
            return [], 0  # no system starts on blank
        if _TIMESTAMP_RE.match(s):
            return [], 0  # timestamp starts a new section, not a system
        if _is_string_line(s):
            break
        if _is_annotation_or_duration(s) or _TS_RE.match(s.strip()):
            block.append((i + 1, s.rstrip("\n")))
            i += 1
            continue
        # Unknown line before strings => not a system start
        return [], 0

    # 2) Now we expect at least one string line
    string_count = 0
    while i < len(lines):
        s = lines[i]
        if not s.strip():
            break
        if _TIMESTAMP_RE.match(s):
            break
        if re.match(r"^\s*(title|artist|capo)\s*:", s, re.IGNORECASE):
            break

        if _is_string_line(s):
            string_count += 1
            block.append((i + 1, s.rstrip("\n")))
            i += 1
            continue

        # allow annotation/duration lines interleaved after strings too
        if _is_annotation_or_duration(s) or _TS_RE.match(s.strip()):
            block.append((i + 1, s.rstrip("\n")))
            i += 1
            continue

        # otherwise end the block
        break

    if string_count == 0:
        return [], 0
    return block, len(block)


def _count_string_lines(block: list[Tuple[int, str]]) -> int:
    return sum(1 for _, ln in block if _is_string_line(ln))


def _is_string_line(line: str) -> bool:
    # Labeled string lines: always strings (E|..., D|..., etc.)
    if _STRING_LABELED_RE.match(line):
        return True

    # Unlabeled lines starting with '|' could be actual strings OR annotations like triplets
    if _STRING_UNLABELED_RE.match(line):
        s = line.strip()

        # Exclude triplet markers like "|-3-|", "| – 3 – |", etc.
        if _TRIPLET_RE.search(s):
            return False

        # Exclude PM marker lines if they ever appear starting with '|'
        if s.startswith("PM"):
            return False

        return True

    return False


def _is_annotation_or_duration(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if _TS_RE.match(s) or _TIMESTAMP_RE.match(s):
        return True
    if "PM" in s:
        return True
    if _TRIPLET_RE.search(s):
        return True
    # duration-ish: contains duration letters and lots of spaces
    if any(ch in DURATION_SYMBOLS for ch in s) and "|" in s:
        return True
    if any(ch in DURATION_SYMBOLS for ch in s) and "|" not in s:
        return True
    return False


def _parse_system_block(
    block: list[Tuple[int, str]], base_line: int, effective_ts: TimeSignature
) -> Tuple[TabSystem, list[ParseWarning]]:
    warnings: list[ParseWarning] = []
    # separate annotation/duration/time-sig lines from string lines
    string_lines: list[Tuple[int, str]] = []
    pre_lines: list[Tuple[int, str]] = []
    for ln_no, ln in block:
        if _is_string_line(ln):
            string_lines.append((ln_no, ln))
        else:
            pre_lines.append((ln_no, ln))

    if not string_lines:
        raise TabParseError("Zero detected string lines in a system.")

    # Determine tuning labels
    labels: list[str] = []
    contents: list[str] = []
    for ln_no, ln in string_lines:
        m = _STRING_LABELED_RE.match(ln)
        if m:
            label = (m.group(1) + (m.group(2) or "")).upper()
            after = ln[m.end() - 1 :]  # include the first '|' in content
            labels.append(label)
            contents.append(after)
        else:
            # unlabeled: default label placeholder
            labels.append("?")
            contents.append(ln.lstrip())

    # If unlabeled and 6 strings, default to EADGBE (top to bottom should be E B G D A E in common tabs;
    # but unlabeled example shows just bars; we pick standard display order labels to stabilize MIDI assumptions).
    if all(label == "?" for label in labels) and len(labels) == 6:
        labels = ["E", "B", "G", "D", "A", "E"]

    # Normalize widths
    width = max(len(c) for c in contents)
    contents = [c.ljust(width) for c in contents]

    # Find duration line (best effort: first pre-line with duration symbols)
    duration_line: Optional[str] = None
    for _, ln in pre_lines:
        if any(ch in DURATION_SYMBOLS for ch in ln):
            duration_line = ln.rstrip("\n").ljust(width)
            break

    # Parse PM spans and triplet spans
    annotations: list[AnnotationSpan] = []
    tuplets: list[TupletSpan] = []
    for ln_no, ln in pre_lines:
        if "PM" in ln:
            # find each "PM....|" segment
            for m in re.finditer(r"PM[-\s]*\|", ln):
                start = m.start()
                end = m.end() - 1
                annotations.append(
                    AnnotationSpan(type="PM", start_col=start, end_col=end)
                )
        # Triplet indicators like "|-3-|" (allow spaces and unicode dashes)
        for m in _TRIPLET_RE.finditer(ln):
            tuplets.append(
                TupletSpan(
                    actual=3,
                    normal=2,
                    start_col=m.start(),
                    end_col=m.end() - 1,  # inclusive end
                )
            )

    # Segment measures using reference line 0
    ref = contents[0]
    bar_matches = list(_find_bar_tokens(ref))
    if len(bar_matches) < 2:
        # If no explicit barlines, treat whole as one measure bounded by synthetic bars
        bar_matches = [(0, 1, "|"), (width - 1, width, "|")]

    # Verify bar tokens exist similarly in other lines (rough check on positions)
    ref_positions = [a for a, _, _ in bar_matches]
    for si, c in enumerate(contents[1:], start=1):
        other_positions = [a for a, _, _ in _find_bar_tokens(c)]
        if other_positions and other_positions != ref_positions:
            warnings.append(
                ParseWarning(
                    line_no=string_lines[si][0],
                    message="Inconsistent barline positions across strings (best-effort parsing).",
                )
            )

    measures: list[Measure] = []
    for j in range(len(bar_matches) - 1):
        left_a, left_b, left_tok = bar_matches[j]
        right_a, right_b, right_tok = bar_matches[j + 1]
        # Measure content columns span from left_b .. right_a
        m_start = left_b
        m_end = right_a
        measure_slices = [c[m_start:m_end] for c in contents]
        dur_slice = duration_line[m_start:m_end] if duration_line else None

        left_bar = _barline_from_token(left_tok)
        right_bar = _barline_from_token(right_tok)

        measure = Measure(
            barline_left=left_bar,
            barline_right=right_bar,
            time_signature=effective_ts,
            events=[],
            raw_columns=len(measure_slices[0]),
        )
        _parse_measure_events(
            measure,
            measure_slices,
            dur_slice,
            tuning=Tuning(labels=labels),
            warnings=warnings,
            base_line=string_lines[0][0],
            col_offset=m_start,
        )
        measures.append(measure)

    system = TabSystem(
        tuning=Tuning(labels=labels),
        measures=measures,
        annotations=annotations,
        tuplets=tuplets,
        duration_line=duration_line,
        raw_lines=[ln for _, ln in pre_lines] + [ln for _, ln in string_lines],
    )
    return system, warnings


def _find_bar_tokens(s: str) -> Iterable[Tuple[int, int, str]]:
    """
    Yields (start_idx, end_idx, token) where token is one of: '||o', 'o||', '||', '*|', '|'.
    Order matters: prefer longer tokens.
    """
    token_re = re.compile(r"\|\|o|o\|\||\|\||\*\||\|")
    for m in token_re.finditer(s):
        yield (m.start(), m.end(), m.group(0))


def _barline_from_token(tok: str) -> Barline:
    if tok == "||o":
        return Barline.REPEAT_START
    if tok == "o||":
        return Barline.REPEAT_END
    if tok == "||":
        return Barline.DOUBLE
    if tok == "*|":
        return Barline.DOUBLE_ENDING
    return Barline.SINGLE


# ---------------- Measure event parsing ----------------

_NOTE_NUM_RE = re.compile(r"\d+")
_GHOST_RE = re.compile(r"\((\d+)\)")


def _parse_measure_events(
    measure: Measure,
    string_slices: list[str],
    dur_slice: Optional[str],
    tuning: Tuning,
    warnings: list[ParseWarning],
    base_line: int,
    col_offset: int,
) -> None:
    if dur_slice is None:
        # Unknown rhythm mode: extract notes in column order with placeholder durations (Q)
        events: list[NoteEvent] = []
        for si, row in enumerate(string_slices):
            c = 0
            while c < len(row):
                ch = row[c]
                if ch.isdigit():
                    m = _NOTE_NUM_RE.match(row, c)
                    assert m
                    fret = int(m.group(0))
                    ne = NoteEvent(
                        start=Fraction(c, 1),
                        duration=Fraction(1, 1),
                        string_index=si,
                        fret=fret,
                    )
                    events.append(ne)
                    c = m.end()
                    continue
                if ch == "(":
                    m = _GHOST_RE.match(row, c)
                    if m:
                        fret = int(m.group(1))
                        ne = NoteEvent(
                            start=Fraction(c, 1),
                            duration=Fraction(1, 1),
                            string_index=si,
                            fret=fret,
                            is_ghost=True,
                        )
                        events.append(ne)
                        c = m.end()
                        continue
                if ch.lower() == "x":
                    ne = NoteEvent(
                        start=Fraction(c, 1),
                        duration=Fraction(1, 1),
                        string_index=si,
                        fret=None,
                        techniques=[Muted()],
                    )
                    events.append(ne)
                    c += 1
                    continue
                c += 1
        # Sort by column position (start encoded as col Fraction)
        events.sort(key=lambda e: (e.start, e.string_index))
        measure.events.extend(events)

        # ✅ assign pitches even in unknown rhythm mode
        _assign_pitches(measure, tuning)
        return

    # Duration-driven mode: walk columns and build time
    time = Fraction(0, 1)
    col = 0
    while col < len(dur_slice):
        parsed = _maybe_parse_duration_at(dur_slice, col)
        if parsed is None:
            col += 1
            continue

        token, consumed = parsed
        token, dur_beats = _duration_token_to_beats(
            token=token, ts=measure.time_signature
        )

        # Find notes at this column on any string
        notes_at_col: list[NoteEvent] = []
        for si, row in enumerate(string_slices):
            note, techniques, _consumed_note = _parse_note_at(row, col)
            if note is None:
                continue
            ne = NoteEvent(
                start=time,
                duration=dur_beats,
                string_index=si,
                fret=note["fret"],
                techniques=techniques,
                tie=TieInfo(True) if token.tie else None,
                grace=token.grace,
                is_ghost=note.get("ghost", False),
            )
            notes_at_col.append(ne)

        if not notes_at_col:
            measure.events.append(RestEvent(start=time, duration=dur_beats))
        elif len(notes_at_col) == 1:
            measure.events.append(notes_at_col[0])
        else:
            measure.events.append(
                ChordEvent(start=time, duration=dur_beats, notes=notes_at_col)
            )

        time += dur_beats
        col += consumed

    # Post-process: compute pitches
    _assign_pitches(measure, tuning)


def _maybe_parse_duration_at(s: str, idx: int) -> Optional[Tuple[DurationToken, int]]:
    """
    Parses duration tokens in a forgiving way.
    Supports:
      + prefix, dots, lowercase (staccato), and Wxn (multibar rest)
    Returns (DurationToken, consumed_columns)
    """
    if idx >= len(s):
        return None

    c = s[idx]
    if c == "+":
        if idx + 1 < len(s) and s[idx + 1] in DURATION_SYMBOLS:
            raw = s[idx] + s[idx + 1]
            k = idx + 2
        else:
            return None
    elif c in DURATION_SYMBOLS:
        raw = s[idx]
        k = idx + 1
    else:
        return None

    # dots
    while k < len(s) and s[k] == ".":
        raw += "."
        k += 1

    # Wxn
    if raw[-1] in ("W", "w") and k < len(s) and s[k] == "x":
        m = re.match(r"x(\d+)", s[k:])
        if m:
            raw += m.group(0)
            k += len(m.group(0))

    consumed = max(1, k - idx)
    return _parse_duration_token(raw), consumed


def _duration_token_to_beats(
    token: DurationToken, ts: TimeSignature
) -> Tuple[DurationToken, Fraction]:
    # quarter-note beat basis
    base_map = {
        "W": Fraction(4, 1),
        "H": Fraction(2, 1),
        "Q": Fraction(1, 1),
        "E": Fraction(1, 2),
        "S": Fraction(1, 4),
        "T": Fraction(1, 8),
        "X": Fraction(1, 16),
        "a": Fraction(0, 1),
    }

    sym = token.symbol.upper()
    dur = base_map.get(sym, Fraction(1, 1))

    # dotted
    if token.dotted == 1:
        dur += dur / 2
    elif token.dotted == 2:
        dur += dur / 2 + dur / 4

    # staccato halves duration (spec)
    if token.staccato and dur > 0:
        dur = dur / 2

    # multibar rest: treat as whole-measure rest repeated n; here store as a single whole-measure rest duration n measures
    if token.multibar_rests:
        # whole-measure in beats depends on time signature denominator
        quarter_per_beat_unit = Fraction(4, ts.denominator)
        measure_beats = Fraction(ts.numerator, 1) * quarter_per_beat_unit
        dur = measure_beats * token.multibar_rests

    return token, dur


def _parse_duration_token(raw: str) -> DurationToken:
    tie = raw.startswith("+")
    core = raw[1:] if tie else raw
    dotted = core.count(".")
    core_nodot = core.replace(".", "")
    multibar_rests = None

    # Wxn
    m = re.match(r"^([WHQESTXawhqestxa])x(\d+)$", core_nodot)
    if m and m.group(1).upper() == "W":
        symbol = m.group(1)
        multibar_rests = int(m.group(2))
    else:
        symbol = core_nodot[0]

    staccato = symbol.islower()
    grace = symbol.lower() == "a"
    return DurationToken(
        raw=raw,
        symbol=symbol,
        dotted=dotted,
        tie=tie,
        staccato=staccato,
        grace=grace,
        multibar_rests=multibar_rests,
    )


def _parse_note_at(row: str, col: int) -> Tuple[Optional[dict], list[Technique], int]:
    """
    Returns (note_dict, techniques, consumed_chars_for_note_token).
    note_dict: {"fret": int|None, "ghost": bool}
    """
    if col >= len(row):
        return None, [], 0

    # slide-in marker just before a digit: "/8" or "\7"
    if row[col] in ("/", "\\") and col + 1 < len(row) and row[col + 1].isdigit():
        m = _NOTE_NUM_RE.match(row, col + 1)
        if not m:
            return None, [], 0
        fret = int(m.group(0))
        return {"fret": fret}, [SlideIn(direction=row[col])], 1 + (m.end() - (col + 1))

    ch = row[col]
    if ch.isdigit():
        m = _NOTE_NUM_RE.match(row, col)
        assert m
        fret = int(m.group(0))
        techniques: list[Technique] = []
        consumed = m.end() - col

        # Inline legato like "0h3" or "1p0": attach technique to destination if we can see it
        # We only do this when contiguous and entirely at this column span.
        if m.end() < len(row):
            nxt = row[m.end()]
            if (
                nxt in ("h", "p")
                and m.end() + 1 < len(row)
                and row[m.end() + 1].isdigit()
            ):
                m2 = _NOTE_NUM_RE.match(row, m.end() + 1)
                if m2:
                    from_fret = fret
                    to_fret = int(m2.group(0))
                    if nxt == "h":
                        techniques.append(
                            HammerOn(from_fret=from_fret, to_fret=to_fret)
                        )
                    else:
                        techniques.append(PullOff(from_fret=from_fret, to_fret=to_fret))
                    # In duration-driven mode, we treat the destination note as occurring at the same rhythmic column.
                    # So we return destination fret here (best-effort).
                    fret = to_fret
                    consumed = m2.end() - col

        # vibrato marker "~" later in the row doesn't align to this col; but in examples it's attached to the same token area.
        # Best-effort: if immediately follows token span.
        if col + consumed < len(row) and row[col + consumed] == "~":
            techniques.append(Vibrato())

        return {"fret": fret}, techniques, consumed

    if ch == "(":
        m = _GHOST_RE.match(row, col)
        if m:
            fret = int(m.group(1))
            return {"fret": fret, "ghost": True}, [], m.end() - col

    if ch.lower() == "x":
        return {"fret": None}, [Muted()], 1

    return None, [], 0


def _assign_pitches(measure: Measure, tuning: Tuning) -> None:
    open_pitches = _tuning_to_open_midi(tuning.labels)
    for ev in measure.events:
        if isinstance(ev, NoteEvent):
            if ev.fret is None:
                ev.pitch = None
            else:
                if 0 <= ev.string_index < len(open_pitches):
                    ev.pitch = open_pitches[ev.string_index] + ev.fret
        elif isinstance(ev, ChordEvent):
            for ne in ev.notes:
                if ne.fret is None:
                    ne.pitch = None
                else:
                    if 0 <= ne.string_index < len(open_pitches):
                        ne.pitch = open_pitches[ne.string_index] + ne.fret


_NOTE_TO_SEMITONE = {
    "C": 0,
    "C#": 1,
    "DB": 1,
    "D": 2,
    "D#": 3,
    "EB": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "GB": 6,
    "G": 7,
    "G#": 8,
    "AB": 8,
    "A": 9,
    "A#": 10,
    "BB": 10,
    "B": 11,
}


def _tuning_to_open_midi(labels_top_to_bottom: list[str]) -> list[int]:
    """
    Best-effort tuning inference:
    - If labels match 6-string standard-ish names, map them to conventional octaves:
      Top-to-bottom for common tabs: E4, B3, G3, D3, A2, E2
    - For alternate tunings, preserve these octaves per string position and change pitch class by label.
    """
    if len(labels_top_to_bottom) == 6:
        default_octaves = [4, 3, 3, 3, 2, 2]
    else:
        # generic: descending from E4-ish
        default_octaves = [4] * len(labels_top_to_bottom)

    result: list[int] = []
    for i, lab in enumerate(labels_top_to_bottom):
        name = lab.strip().upper()
        # normalize accidentals
        if len(name) >= 2 and name[1] in ("#", "B"):
            key = name[0] + name[1]
        else:
            key = name[0] if name else "E"
        semitone = _NOTE_TO_SEMITONE.get(key, _NOTE_TO_SEMITONE["E"])
        octave = default_octaves[i] if i < len(default_octaves) else 3
        midi = 12 * (octave + 1) + semitone
        result.append(midi)
    return result


# Patch wrapper cleanly without metaprogramming surprises:
def _maybe_parse_duration_at_raw(s: str, idx: int) -> Optional[Tuple[str, int]]:
    if idx >= len(s):
        return None
    c = s[idx]
    if c == "+":
        if idx + 1 >= len(s) or s[idx + 1] not in DURATION_SYMBOLS:
            return None
    elif c not in DURATION_SYMBOLS:
        return None

    raw = s[idx]
    k = idx + 1
    if c == "+":
        raw += s[idx + 1]
        k = idx + 2

    while k < len(s) and s[k] == ".":
        raw += "."
        k += 1

    if len(raw) >= 1 and raw[-1] in ("W", "w") and k < len(s) and s[k] == "x":
        m = re.match(r"x(\d+)", s[k:])
        if m:
            raw += m.group(0)
            k += len(m.group(0))

    return raw, max(1, k - idx)
