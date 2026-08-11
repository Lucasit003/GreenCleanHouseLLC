"""Audio extraction and media probing via ffmpeg/ffprobe."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import tempfile

FFMPEG_INSTALL_HINT = (
    "ffmpeg and ffprobe are required but were not found on PATH.\n"
    "Install them and try again:\n"
    "  macOS:          brew install ffmpeg\n"
    "  Debian/Ubuntu:  sudo apt-get install ffmpeg\n"
    "  Fedora:         sudo dnf install ffmpeg\n"
    "  Windows:        winget install Gyan.FFmpeg\n"
    "  Or download a build from https://ffmpeg.org/download.html"
)


def check_ffmpeg() -> None:
    """Exit with an actionable message if ffmpeg or ffprobe is missing."""
    missing = [b for b in ("ffmpeg", "ffprobe") if shutil.which(b) is None]
    if missing:
        raise SystemExit(f"Missing: {', '.join(missing)}\n\n{FFMPEG_INSTALL_HINT}")


def probe_duration(video_path: str) -> float:
    """Return the container duration of the source video in seconds."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            video_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"ffprobe failed on {video_path}:\n{result.stderr.strip()}\n"
            "Is the file a readable video?"
        )
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read duration from ffprobe output: {exc}")


def probe_video_size(video_path: str) -> tuple[int, int]:
    """Return (width, height) of the first video stream."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            video_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"ffprobe failed on {video_path}:\n{result.stderr.strip()}"
        )
    try:
        stream = json.loads(result.stdout)["streams"][0]
        return int(stream["width"]), int(stream["height"])
    except (KeyError, IndexError, ValueError, json.JSONDecodeError):
        raise SystemExit(f"No video stream found in {video_path}.")


@contextlib.contextmanager
def extracted_audio(video_path: str):
    """Stream 16kHz mono WAV out of the video into a temp file.

    The video is never loaded into memory — ffmpeg streams through it. The
    temp file is deleted when the context exits.
    """
    fd, wav_path = tempfile.mkstemp(suffix=".wav", prefix="clipper_")
    os.close(fd)
    try:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            video_path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-acodec",
            "pcm_s16le",
            wav_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit(
                f"ffmpeg failed to extract audio from {video_path}:\n"
                f"{result.stderr.strip()}"
            )
        if os.path.getsize(wav_path) == 0:
            raise SystemExit(
                f"No audio track found in {video_path}. "
                "This tool needs speech to work with."
            )
        yield wav_path
    finally:
        with contextlib.suppress(OSError):
            os.remove(wav_path)
