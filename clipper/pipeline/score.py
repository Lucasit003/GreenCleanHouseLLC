"""Candidate windowing and LLM scoring."""

from __future__ import annotations

import json
import os
import re

from .models import Candidate, Segment, Word

TARGET_MIN = 30.0
TARGET_MAX = 75.0
HARD_MIN = 20.0
HARD_MAX = 90.0

BATCH_SIZE = 10
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a short-form content editor. You cut clips from long \
videos for TikTok, Reels, and Shorts, and you have a sharp eye for which moments \
survive on their own with no surrounding context.

Score each candidate on how well it works as a standalone short-form clip. Weight:
- A hook in the first 3 seconds. The opening line has to earn the next 10 seconds.
- A complete thought with a payoff. The clip should land somewhere.
- No dangling references to things said earlier in the video ("as I mentioned",
  "that guy", "the second thing") that a cold viewer cannot resolve.

Penalize clips that start mid-explanation or end without resolution. A clip that
is merely interesting-in-context but confusing cold is a low score.

Return ONLY a JSON array. No prose, no markdown fences. Each element:
{"index": <int, the candidate index given to you>,
 "score": <int 1-10>,
 "reason": "<one short sentence>",
 "title": "<3-6 word slug-friendly title>"}"""


def build_candidates(segments: list[Segment], words: list[Word]) -> list[Candidate]:
    """Slide a window over sentence boundaries to build candidate clips.

    Whisper's segment boundaries are a reasonable proxy for sentence boundaries,
    so windows always snap to them. Windows overlap by roughly 50% so a good
    moment straddling a boundary is not missed.
    """
    if not segments:
        return []

    candidates: list[Candidate] = []
    seen: set[tuple[float, float]] = set()
    i = 0

    while i < len(segments):
        start = segments[i].start
        window: list[Segment] = []
        picked_lengths: list[float] = []
        first_valid_count = 0

        for j in range(i, len(segments)):
            window.append(segments[j])
            duration = segments[j].end - start
            if duration > TARGET_MAX:
                break
            if duration < TARGET_MIN:
                continue

            # Keep a spread of lengths per start point rather than every
            # possible end: one as soon as we clear the minimum, then roughly
            # one per 15 seconds of extra length.
            if not picked_lengths or duration - picked_lengths[-1] >= 15.0:
                key = (round(start, 2), round(segments[j].end, 2))
                if key not in seen:
                    seen.add(key)
                    candidates.append(
                        Candidate(
                            start=start,
                            end=segments[j].end,
                            text=" ".join(s.text for s in window).strip(),
                        )
                    )
                picked_lengths.append(duration)
                if not first_valid_count:
                    first_valid_count = len(window)

        # Advance by half the shortest valid window for ~50% overlap.
        step = max(1, first_valid_count // 2) if first_valid_count else 1
        i += step

    return [c for c in candidates if HARD_MIN <= c.duration <= HARD_MAX]


def _strip_fences(text: str) -> str:
    """Remove markdown code fences the model may have added anyway."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_batch_response(text: str) -> list[dict]:
    data = json.loads(_strip_fences(text))
    if not isinstance(data, list):
        raise ValueError("expected a JSON array")
    return data


def _batch_prompt(batch: list[tuple[int, Candidate]]) -> str:
    lines = ["Score these candidate clips:", ""]
    for index, cand in batch:
        lines.append(f"--- candidate {index} ---")
        lines.append(f"duration: {cand.duration:.1f}s")
        lines.append(f"transcript: {cand.text}")
        lines.append("")
    lines.append(
        f"Return a JSON array with exactly {len(batch)} objects, one per candidate, "
        "using the candidate indexes shown above."
    )
    return "\n".join(lines)


def score_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Score candidates with the Anthropic API, 10 per request."""
    if not candidates:
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set.\n"
            "Put it in a .env file next to clip.py:\n"
            "  ANTHROPIC_API_KEY=sk-ant-...\n"
            "See .env.example for the format."
        )

    try:
        import anthropic
    except ImportError:
        raise SystemExit(
            "anthropic is not installed.\n"
            "Install dependencies with: pip install -r requirements.txt"
        )

    client = anthropic.Anthropic(api_key=api_key)
    indexed = list(enumerate(candidates))
    scored: list[Candidate] = []

    for offset in range(0, len(indexed), BATCH_SIZE):
        batch = indexed[offset : offset + BATCH_SIZE]
        batch_no = offset // BATCH_SIZE + 1
        total_batches = (len(indexed) + BATCH_SIZE - 1) // BATCH_SIZE
        results = None

        for attempt in (1, 2):
            try:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=4000,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": _batch_prompt(batch)}],
                )
                text = "".join(
                    block.text for block in response.content if block.type == "text"
                )
                results = _parse_batch_response(text)
                break
            except (json.JSONDecodeError, ValueError) as exc:
                if attempt == 1:
                    print(f"  batch {batch_no}/{total_batches}: bad JSON ({exc}); retrying")
                else:
                    print(f"  batch {batch_no}/{total_batches}: bad JSON again; skipping batch")
            except anthropic.APIError as exc:
                if attempt == 1:
                    print(f"  batch {batch_no}/{total_batches}: API error ({exc}); retrying")
                else:
                    print(f"  batch {batch_no}/{total_batches}: API error again; skipping batch")

        if not results:
            continue

        by_index = {i: c for i, c in batch}
        for item in results:
            try:
                cand = by_index.get(int(item["index"]))
                if cand is None:
                    continue
                cand.score = max(1, min(10, int(item["score"])))
                cand.reason = str(item.get("reason", "")).strip()
                cand.title = str(item.get("title", "")).strip()
            except (KeyError, TypeError, ValueError):
                continue
            scored.append(cand)

    return scored


def _overlap_fraction(a: Candidate, b: Candidate) -> float:
    overlap = min(a.end, b.end) - max(a.start, b.start)
    if overlap <= 0:
        return 0.0
    shorter = min(a.duration, b.duration)
    return overlap / shorter if shorter > 0 else 0.0


def deduplicate(candidates: list[Candidate], max_overlap: float = 0.30) -> list[Candidate]:
    """Greedily pick the best non-overlapping candidates.

    Windows overlap by design, so the top scorers cluster around the same
    moment. Walk down by score and drop anything that overlaps an already
    selected clip by more than `max_overlap`.
    """
    selected: list[Candidate] = []
    for cand in sorted(candidates, key=lambda c: (-c.score, c.start)):
        if any(_overlap_fraction(cand, chosen) > max_overlap for chosen in selected):
            continue
        selected.append(cand)
    return selected
