"""Shared data structures for the clipper pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Word:
    text: str
    start: float
    end: float

    def to_dict(self) -> dict:
        return {"text": self.text, "start": self.start, "end": self.end}

    @classmethod
    def from_dict(cls, d: dict) -> "Word":
        return cls(text=d["text"], start=float(d["start"]), end=float(d["end"]))


@dataclass
class Segment:
    text: str
    start: float
    end: float

    def to_dict(self) -> dict:
        return {"text": self.text, "start": self.start, "end": self.end}

    @classmethod
    def from_dict(cls, d: dict) -> "Segment":
        return cls(text=d["text"], start=float(d["start"]), end=float(d["end"]))


@dataclass
class Candidate:
    """A window of the transcript that might work as a standalone clip."""

    start: float
    end: float
    text: str

    # Filled in by score.py
    score: int = 0
    reason: str = ""
    title: str = ""

    # Filled in by cut.py
    refined_start: float | None = None
    refined_end: float | None = None
    words: list[Word] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def cut_start(self) -> float:
        return self.start if self.refined_start is None else self.refined_start

    @property
    def cut_end(self) -> float:
        return self.end if self.refined_end is None else self.refined_end

    @property
    def cut_duration(self) -> float:
        return self.cut_end - self.cut_start


@dataclass
class Clip:
    """A rendered clip, as recorded in clips.json."""

    filename: str
    score: int
    reason: str
    title: str
    source_start: float
    source_end: float
    duration: float
    text: str

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "score": self.score,
            "reason": self.reason,
            "title": self.title,
            "source_start": round(self.source_start, 3),
            "source_end": round(self.source_end, 3),
            "duration": round(self.duration, 3),
            "text": self.text,
        }
