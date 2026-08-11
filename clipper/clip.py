#!/usr/bin/env python3
"""Extract short vertical clips with burned-in captions from a long video."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time

from dotenv import load_dotenv

from pipeline import cut, render, score, transcribe
from pipeline.audio import (
    check_ffmpeg,
    extracted_audio,
    probe_duration,
    probe_video_size,
)

OUTPUT_DIR = "./clips"


class Stage:
    """Prints a stage banner on entry and the elapsed time on exit."""

    def __init__(self, name: str):
        self.name = name

    def __enter__(self):
        print(f"[{self.name}] starting")
        self.t0 = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            print(f"[{self.name}] done in {time.monotonic() - self.t0:.1f}s")
        return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="clip.py",
        description="Extract short vertical clips from a long video.",
    )
    parser.add_argument("video_path", help="Path to the source mp4")
    parser.add_argument(
        "--count", type=int, default=8, help="Max clips to produce (default: 8)"
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=6,
        help="Discard candidates scoring below this (default: 6)",
    )
    parser.add_argument(
        "--model", default="base", help="Whisper model size (default: base)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Transcribe and score, print the ranked list, render nothing",
    )
    return parser.parse_args(argv)


def print_ranked(candidates: list) -> None:
    print()
    print(f"{'score':>5}  {'start':>9}  {'end':>9}  {'len':>6}  title / reason")
    print("-" * 78)
    for cand in candidates:
        print(
            f"{cand.score:>5}  {cand.cut_start:>9.1f}  {cand.cut_end:>9.1f}  "
            f"{cand.cut_duration:>5.1f}s  {cand.title}"
        )
        print(f"{'':>5}  {'':>9}  {'':>9}  {'':>6}  {cand.reason}")
    print()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_dotenv()
    check_ffmpeg()

    video_path = args.video_path
    if not os.path.isfile(video_path):
        raise SystemExit(f"No such file: {video_path}")

    run_start = time.monotonic()
    duration = probe_duration(video_path)
    print(f"Source: {video_path} ({duration / 60:.1f} min)")

    # --- Stages 1 & 2: audio extraction + transcription -------------------
    cache_path = transcribe.cache_path_for(video_path)
    words = segments = None

    if transcribe.cache_is_fresh(video_path, cache_path):
        with Stage("transcribe"):
            print(f"  using cached transcript: {cache_path}")
            try:
                words, segments = transcribe.load_cache(cache_path)
            except Exception as exc:  # noqa: BLE001 - fall back to re-transcribing
                print(f"  cache unreadable ({exc}); re-transcribing")
                words = segments = None

    if words is None:
        # The temp wav lives only as long as this stack; transcription reads it.
        with contextlib.ExitStack() as stack:
            with Stage("extract audio"):
                audio_path = stack.enter_context(extracted_audio(video_path))
            with Stage("transcribe"):
                print(f"  whisper model: {args.model}")
                words, segments = transcribe.transcribe(
                    video_path, audio_path, args.model
                )
                print(f"  cached transcript: {cache_path}")

    print(f"  {len(words)} words, {len(segments)} segments")

    # --- Stage 3: candidates + scoring ------------------------------------
    with Stage("score"):
        candidates = score.build_candidates(segments, words)
        print(f"  {len(candidates)} candidate windows")
        if not candidates:
            raise SystemExit(
                "No candidate windows in the 20-90s range. "
                "Is this video long enough, and does it contain continuous speech?"
            )
        scored = score.score_candidates(candidates)
        print(f"  {len(scored)} scored")
        kept = [c for c in scored if c.score >= args.min_score]
        print(f"  {len(kept)} at or above --min-score {args.min_score}")
        selected = score.deduplicate(kept)[: args.count]
        print(f"  {len(selected)} selected after dedup")

    if not selected:
        print("\nNothing scored high enough. Try lowering --min-score.")
        return 1

    # --- Stage 4: cut point refinement ------------------------------------
    with Stage("refine cuts"):
        selected = cut.refine_all(selected, words, duration)
        selected.sort(key=lambda c: (-c.score, c.cut_start))
        print(f"  {len(selected)} clips with usable boundaries")

    if not selected:
        print("\nNo candidate survived boundary refinement.")
        return 1

    if args.dry_run:
        print_ranked(selected)
        print(f"Dry run — nothing rendered. Total {time.monotonic() - run_start:.1f}s")
        return 0

    # --- Stages 5 & 6: render + manifest ----------------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    source_size = probe_video_size(video_path)
    records = []

    with Stage("render"):
        print(f"  source {source_size[0]}x{source_size[1]} -> 1080x1920")
        for i, cand in enumerate(selected, start=1):
            filename = render.clip_filename(cand, i)
            out_path = os.path.join(OUTPUT_DIR, filename)
            print(f"  [{i}/{len(selected)}] {filename} ({cand.cut_duration:.1f}s)")
            try:
                render.render_clip(video_path, cand, out_path, source_size)
            except RuntimeError as exc:
                print(f"  !! {exc}")
                continue
            records.append(render.to_clip_record(cand, filename).to_dict())

    manifest_path = os.path.join(OUTPUT_DIR, "clips.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)

    print(f"\n{len(records)} clips in {OUTPUT_DIR}/ (manifest: {manifest_path})")
    print(f"Total {time.monotonic() - run_start:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
