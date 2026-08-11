"""Boundary refinement: snap cut points to word edges and silent gaps."""

from __future__ import annotations

from bisect import bisect_left

from .models import Candidate, Word

START_PAD = 0.150
END_PAD = 0.300
GAP_THRESHOLD = 0.200


def refine(candidate: Candidate, words: list[Word], video_duration: float) -> bool:
    """Snap a candidate's boundaries to word edges. Returns False if unusable.

    Never lets a clip start or end mid-word. Where there is a gap of at least
    200ms next to a boundary, the cut lands inside that gap instead of tight
    against the speech.
    """
    if not words:
        return False

    starts = [w.start for w in words]

    first = bisect_left(starts, candidate.start - 1e-6)
    if first >= len(words):
        return False

    last = first
    while last + 1 < len(words) and words[last + 1].end <= candidate.end + 1e-6:
        last += 1
    if words[last].end > candidate.end + 1e-6 and last > first:
        last -= 1
    if last < first:
        return False

    start = words[first].start - START_PAD
    if first > 0:
        gap = words[first].start - words[first - 1].end
        if gap >= GAP_THRESHOLD:
            start = words[first - 1].end + gap / 2
        else:
            # Stay clear of the previous word even if the pad would overrun it.
            start = max(start, words[first - 1].end)

    end = words[last].end + END_PAD
    if last + 1 < len(words):
        gap = words[last + 1].start - words[last].end
        if gap >= GAP_THRESHOLD:
            end = words[last].end + gap / 2
        else:
            end = min(end, words[last + 1].start)

    start = max(0.0, start)
    end = min(video_duration, end)
    if end - start <= 0:
        return False

    candidate.refined_start = start
    candidate.refined_end = end
    candidate.words = words[first : last + 1]
    candidate.text = " ".join(w.text for w in candidate.words).strip()
    return True


def refine_all(
    candidates: list[Candidate], words: list[Word], video_duration: float
) -> list[Candidate]:
    return [c for c in candidates if refine(c, words, video_duration)]
