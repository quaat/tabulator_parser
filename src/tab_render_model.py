from __future__ import annotations

from fractions import Fraction
from typing import List, Optional, Tuple

from .tab_model import (
    Barline,
    ChordEvent,
    NoteEvent,
    RestEvent,
    TabScore,
)


def render_tab_from_model(score: TabScore) -> str:
    out: list[str] = []
    out.append(f"title: {score.title}")
    out.append(f"artist: {score.artist}")
    if score.capo is not None:
        out.append(f"capo: {score.capo}")
    out.append("")

    for section in score.sections:
        if section.timestamp:
            out.append(section.timestamp)
        if section.time_signature:
            out.append(
                f"{section.time_signature.numerator}/{section.time_signature.denominator}"
            )

        for system in section.systems:
            lines = _render_system(system)
            out.extend(lines)
            out.append("")

    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def _render_system(system) -> List[str]:
    labels = system.tuning.labels
    n_strings = len(labels)

    # Build per-measure grids, then concatenate with bar tokens.
    rendered_measures = []
    duration_line_present = False

    for m in system.measures:
        grid, dur = _render_measure(m, n_strings)
        rendered_measures.append((m, grid, dur))
        if dur is not None:
            duration_line_present = True

    # Concatenate
    # Determine final string lines
    string_lines = [""] * n_strings
    dur_line = ""

    for m, grid, dur in rendered_measures:
        left = _bar_token(m.barline_left)
        right = _bar_token(m.barline_right)

        # Each measure segment: left bar already included by previous right?
        # We emit left for the first measure, otherwise we only emit content + right.
        # For simplicity: emit left for each measure and let it be explicit.
        for si in range(n_strings):
            string_lines[si] += left + "".join(grid[si]) + right

        if duration_line_present:
            dur_line += " " * len(left)
            dur_line += "".join(dur) if dur is not None else (" " * len(grid[0]))
            dur_line += " " * len(right)

    # Prefix tuning labels
    out: list[str] = []
    if duration_line_present:
        out.append("   " + dur_line.rstrip())

    for si in range(n_strings):
        out.append(f"{labels[si]}{string_lines[si]}")

    return out


def _render_measure(
    measure, n_strings: int
) -> Tuple[List[List[str]], Optional[List[str]]]:
    width = measure.raw_columns or _infer_measure_width(measure)
    grid = [["-"] * width for _ in range(n_strings)]

    # If events look like rhythm mode, build a duration line
    duration_line: Optional[List[str]] = None
    if _has_rhythm_mode(measure):
        duration_line = [" "] * width

    # Determine mapping from musical start -> column
    col_map = _make_time_to_col_mapper(measure, width)

    for ev in measure.events:
        if isinstance(ev, RestEvent):
            if duration_line is not None:
                c = col_map(ev.start)
                _place_token(duration_line, c, _duration_symbol_for(ev.duration))
            continue

        if isinstance(ev, NoteEvent):
            c = col_map(ev.start)
            _place_note(grid, ev.string_index, c, ev)
            if duration_line is not None:
                _place_token(duration_line, c, _duration_symbol_for(ev.duration))
            continue

        if isinstance(ev, ChordEvent):
            c = col_map(ev.start)
            for ne in ev.notes:
                _place_note(grid, ne.string_index, c, ne)
            if duration_line is not None:
                _place_token(duration_line, c, _duration_symbol_for(ev.duration))

    return grid, duration_line


def _place_note(
    grid: List[List[str]], string_index: int, col: int, ne: NoteEvent
) -> None:
    if string_index < 0 or string_index >= len(grid):
        return
    row = grid[string_index]

    if col < 0 or col >= len(row):
        return

    if ne.fret is None:
        _place_token(row, col, "x")
        return

    if ne.is_ghost:
        token = f"({ne.fret})"
    else:
        token = str(ne.fret)

    _place_token(row, col, token)


def _place_token(row: List[str], col: int, token: str) -> None:
    # Best-effort overlay; avoid going out of bounds
    for i, ch in enumerate(token):
        idx = col + i
        if 0 <= idx < len(row):
            row[idx] = ch


def _bar_token(b: Barline) -> str:
    return str(b.value)


def _infer_measure_width(measure) -> int:
    # fallback: approximate width by max number of events * 3
    n = max(8, len(measure.events) * 3)
    return min(max(n, 16), 96)


def _has_rhythm_mode(measure) -> bool:
    # Heuristic: in unknown rhythm mode, start is often a large integer column offset
    # In rhythm mode, start is typically small beat fractions (0, 1/2, 1, ...)
    starts = [ev.start for ev in measure.events if hasattr(ev, "start")]
    if not starts:
        return False
    return all(isinstance(s, Fraction) and s < 64 for s in starts)


def _make_time_to_col_mapper(measure, width: int):
    # If unknown rhythm mode, starts are already "columns"
    if not _has_rhythm_mode(measure):

        def f(t: Fraction) -> int:
            return int(t)  # t is a column index encoded as Fraction

        return f

    # Rhythm mode: map measure time range to width
    total = sum((ev.duration for ev in measure.events), Fraction(0, 1))
    if total <= 0:
        total = Fraction(4, 1)

    def f(t: Fraction) -> int:
        # proportional mapping
        x = float(t / total) if total else 0.0
        c = int(round(x * (width - 1)))
        return max(0, min(width - 1, c))

    return f


def _duration_symbol_for(d: Fraction) -> str:
    # Quarter-note beat basis (same as parser)
    if d == Fraction(4, 1):
        return "W"
    if d == Fraction(2, 1):
        return "H"
    if d == Fraction(1, 1):
        return "Q"
    if d == Fraction(1, 2):
        return "E"
    if d == Fraction(1, 4):
        return "S"
    if d == Fraction(1, 8):
        return "T"
    if d == Fraction(1, 16):
        return "X"
    return "Q"  # fallback
