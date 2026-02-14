from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from typing import Any, Optional, Union


@dataclass(frozen=True)
class TimeSignature:
    numerator: int
    denominator: int

    def __str__(self) -> str:
        return f"{self.numerator}/{self.denominator}"


class Barline(str, Enum):
    SINGLE = "|"
    DOUBLE = "||"
    REPEAT_START = "||o"
    REPEAT_END = "o||"
    DOUBLE_ENDING = "*|"


@dataclass(frozen=True)
class ParseWarning:
    line_no: int
    message: str


# --- Techniques / Notations ---


@dataclass(frozen=True)
class Technique:
    pass


@dataclass(frozen=True)
class HammerOn(Technique):
    from_fret: Optional[int]
    to_fret: Optional[int]


@dataclass(frozen=True)
class PullOff(Technique):
    from_fret: Optional[int]
    to_fret: Optional[int]


@dataclass(frozen=True)
class SlideIn(Technique):
    direction: str  # "/" or "\"


@dataclass(frozen=True)
class Vibrato(Technique):
    pass


@dataclass(frozen=True)
class Muted(Technique):
    pass


@dataclass(frozen=True)
class UnknownTechnique(Technique):
    raw: str


@dataclass(frozen=True)
class TieInfo:
    continued: bool = True


@dataclass(frozen=True)
class DurationToken:
    raw: str  # e.g. "+H.", "q", "E", "Wxn"
    symbol: str  # W H Q E S T X a (case preserved)
    dotted: int = 0  # 0,1,2
    tie: bool = False
    staccato: bool = False
    grace: bool = False
    multibar_rests: Optional[int] = None


@dataclass(frozen=True)
class TupletSpan:
    actual: int
    normal: int
    start_col: int
    end_col: int


@dataclass(frozen=True)
class AnnotationSpan:
    type: str  # "PM", etc.
    start_col: int
    end_col: int


# --- Events ---


@dataclass
class Event:
    start: Fraction
    duration: Fraction
    notations: list[Any] = field(default_factory=list)


@dataclass
class NoteEvent(Event):
    string_index: int = 0
    fret: Optional[int] = None  # None for muted/non-pitched
    techniques: list[Technique] = field(default_factory=list)
    tie: Optional[TieInfo] = None
    grace: bool = False
    pitch: Optional[int] = None
    is_ghost: bool = False


@dataclass
class ChordEvent(Event):
    notes: list[NoteEvent] = field(default_factory=list)


@dataclass
class RestEvent(Event):
    pass


# --- Measure / System / Score ---


@dataclass
class Measure:
    barline_left: Barline
    barline_right: Barline
    time_signature: TimeSignature
    events: list[Union[NoteEvent, ChordEvent, RestEvent]] = field(default_factory=list)
    raw_columns: Optional[int] = None


@dataclass(frozen=True)
class Tuning:
    labels: list[str]  # top-to-bottom labels like ["D","A","F","D","A","D"]


@dataclass
class TabSystem:
    tuning: Tuning
    measures: list[Measure] = field(default_factory=list)
    annotations: list[AnnotationSpan] = field(default_factory=list)
    tuplets: list[TupletSpan] = field(default_factory=list)
    duration_line: Optional[str] = None  # stored padded grid line (best-effort)
    raw_lines: list[str] = field(default_factory=list)  # for round-trip rendering


@dataclass
class Section:
    timestamp: Optional[str] = None  # "mm:ss"
    time_signature: Optional[TimeSignature] = (
        None  # declared at section start (may be None)
    )
    systems: list[TabSystem] = field(default_factory=list)


@dataclass
class TabScore:
    title: str
    artist: str
    capo: Optional[int]
    sections: list[Section] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# --- MIDI ---


@dataclass(frozen=True)
class MidiEvent:
    time_sec: float
    type: str  # "note_on" | "note_off"
    pitch: int
    velocity: int = 90
    channel: int = 0
