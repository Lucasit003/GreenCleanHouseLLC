"""Whisper transcription with an on-disk cache next to the source video."""

from __future__ import annotations

import json
import os

from .models import Segment, Word


def cache_path_for(video_path: str) -> str:
    base, _ = os.path.splitext(video_path)
    return f"{base}.transcript.json"


def load_cache(cache_path: str) -> tuple[list[Word], list[Segment]]:
    with open(cache_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    words = [Word.from_dict(w) for w in data["words"]]
    segments = [Segment.from_dict(s) for s in data["segments"]]
    return words, segments


def _save_cache(cache_path: str, words: list[Word], segments: list[Segment]) -> None:
    payload = {
        "words": [w.to_dict() for w in words],
        "segments": [s.to_dict() for s in segments],
    }
    with open(cache_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)


def cache_is_fresh(video_path: str, cache_path: str) -> bool:
    """True when a cache exists and the source has not changed since."""
    if not os.path.exists(cache_path):
        return False
    return os.path.getmtime(video_path) <= os.path.getmtime(cache_path)


def transcribe(
    video_path: str, audio_path: str, model_size: str
) -> tuple[list[Word], list[Segment]]:
    """Run faster-whisper with word timestamps and cache the result."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit(
            "faster-whisper is not installed.\n"
            "Install dependencies with: pip install -r requirements.txt"
        )

    try:
        model = WhisperModel(model_size, device="auto", compute_type="default")
    except Exception as exc:  # noqa: BLE001 - surface any load failure clearly
        raise SystemExit(
            f"Could not load the Whisper model {model_size!r}: {exc}\n\n"
            "The first run downloads the weights from huggingface.co, so this "
            "usually means one of:\n"
            "  - No network access, or a proxy/firewall blocking huggingface.co\n"
            "  - An unknown model name. Valid sizes: tiny, base, small, medium,\n"
            "    large-v2, large-v3 (with optional .en variants)\n\n"
            "To run fully offline, download a faster-whisper model once on a\n"
            "connected machine and pass the directory instead:\n"
            f"  python clip.py <video> --model /path/to/faster-whisper-{model_size}"
        )

    segment_iter, _info = model.transcribe(audio_path, word_timestamps=True)

    words: list[Word] = []
    segments: list[Segment] = []
    for seg in segment_iter:
        text = seg.text.strip()
        if text:
            segments.append(Segment(text=text, start=float(seg.start), end=float(seg.end)))
        for w in seg.words or []:
            token = w.word.strip()
            if not token:
                continue
            words.append(Word(text=token, start=float(w.start), end=float(w.end)))

    if not words:
        raise SystemExit(
            "Whisper produced no words for this file. "
            "Check that the video actually contains speech."
        )

    _save_cache(cache_path_for(video_path), words, segments)
    return words, segments
