"""Rendering: one ffmpeg call per clip does trim, 9:16 crop, and caption burn."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile

from .models import Candidate, Clip, Word

OUT_W = 1080
OUT_H = 1920
WORDS_PER_CAPTION = 2
CAPTION_HEIGHT_FRACTION = 0.60  # from the top of the frame

# Arial exists on macOS and Windows, and fontconfig substitutes a metric
# equivalent (Liberation Sans / DejaVu Sans) on Linux. A Linux-only family
# name here would silently fall back to an arbitrary font elsewhere.
CAPTION_FONT = "Arial"

ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {OUT_W}
PlayResY: {OUT_H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{CAPTION_FONT},96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,0,2,60,60,{int(OUT_H * (1 - CAPTION_HEIGHT_FRACTION))},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def slugify(text: str, fallback: str = "clip") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or fallback


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{int(hours)}:{int(minutes):02d}:{secs:05.2f}"


def _ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def build_ass(words: list[Word], clip_start: float, clip_duration: float) -> str:
    """Two words on screen at a time, timed relative to the clip start."""
    lines = [ASS_HEADER]
    for i in range(0, len(words), WORDS_PER_CAPTION):
        group = words[i : i + WORDS_PER_CAPTION]
        start = max(0.0, group[0].start - clip_start)
        end = min(clip_duration, group[-1].end - clip_start)
        # A group lying wholly outside the clip has nothing to show. Emitting
        # it anyway would produce a Dialogue line whose end precedes its start.
        if start >= clip_duration or end <= 0:
            continue
        if end <= start:
            end = min(clip_duration, start + 0.2)
        if end <= start:
            continue
        text = _ass_escape(" ".join(w.text for w in group))
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Caption,,0,0,0,,{text}"
        )
    return "\n".join(lines) + "\n"


def crop_rect(width: int, height: int) -> tuple[int, int, int, int]:
    """Largest centered 9:16 rectangle that fits inside the source frame."""
    crop_w = min(width, int(round(height * 9 / 16)))
    crop_h = min(height, int(round(width * 16 / 9)))
    crop_w -= crop_w % 2
    crop_h -= crop_h % 2
    x = max(0, (width - crop_w) // 2)
    y = max(0, (height - crop_h) // 2)
    return crop_w, crop_h, x, y


def render_clip(
    video_path: str,
    candidate: Candidate,
    out_path: str,
    source_size: tuple[int, int],
) -> None:
    """Trim, center-crop to 9:16, scale to 1080x1920, burn captions — one call."""
    start = candidate.cut_start
    duration = candidate.cut_duration
    crop_w, crop_h, x, y = crop_rect(*source_size)

    with tempfile.TemporaryDirectory(prefix="clipper_ass_") as workdir:
        ass_name = "captions.ass"
        with open(os.path.join(workdir, ass_name), "w", encoding="utf-8") as fh:
            fh.write(build_ass(candidate.words, start, duration))

        vf = (
            f"crop={crop_w}:{crop_h}:{x}:{y},"
            f"scale={OUT_W}:{OUT_H},setsar=1,"
            f"subtitles={ass_name}"
        )
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            os.path.abspath(video_path),
            "-t",
            f"{duration:.3f}",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            os.path.abspath(out_path),
        ]
        result = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed rendering {os.path.basename(out_path)}:\n"
                f"{result.stderr.strip()}"
            )


def clip_filename(candidate: Candidate, index: int) -> str:
    slug = slugify(candidate.title, fallback=f"clip-{index:02d}")
    return f"{candidate.score:02d}_{slug}.mp4"


def to_clip_record(candidate: Candidate, filename: str) -> Clip:
    return Clip(
        filename=filename,
        score=candidate.score,
        reason=candidate.reason,
        title=candidate.title,
        source_start=candidate.cut_start,
        source_end=candidate.cut_end,
        duration=candidate.cut_duration,
        text=candidate.text,
    )
