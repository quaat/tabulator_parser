from __future__ import annotations

from .tab_model import TabScore


def render_tab(score: TabScore) -> str:
    """
    Round-trip oriented renderer:
    - Always emits header (title/artist/capo).
    - Emits each system largely as originally parsed (stored raw lines),
      trimming only trailing whitespace for cleanliness.

    This is intentionally conservative to keep parse→render→parse stable.
    """
    out: list[str] = []
    out.append(f"title: {score.title}")
    out.append(f"artist: {score.artist}")
    if score.capo is not None:
        out.append(f"capo: {score.capo}")
    out.append("")  # blank line after header

    for section in score.sections:
        if section.timestamp:
            out.append(f"{section.timestamp}")
        if section.time_signature:
            out.append(
                f"{section.time_signature.numerator}/{section.time_signature.denominator}"
            )
        for system in section.systems:
            for ln in system.raw_lines:
                out.append(ln.rstrip())
            out.append("")  # blank line between systems

    # strip trailing blank lines
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"
