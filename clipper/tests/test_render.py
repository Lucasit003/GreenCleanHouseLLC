"""End-to-end test of the CLI: real ffmpeg, real encode, stubbed scoring.

Skipped when ffmpeg/ffprobe are not installed. Builds a synthetic video and a
fabricated transcript cache so the run exercises windowing, refinement,
rendering, and the manifest without needing whisper weights or an API key.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

VOCAB = (
    "the reason nobody ships is they wait for permission that never arrives "
    "and honestly that is the whole thing right there so just go build it "
    "today before you talk yourself out of it again"
).split()


def _make_video(path, seconds=90, width=640, height=360):
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size={width}x{height}:rate=10:duration={seconds}",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "40",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "32k", path,
        ],
        check=True,
        capture_output=True,
    )


def _write_transcript_cache(video_path, seconds=90):
    """Evenly paced words with a pause between sentences."""
    words, segments = [], []
    t, k = 0.5, 0
    while t < seconds - 4:
        seg_words = []
        wt = t
        for _ in range(8):
            seg_words.append(
                {"text": VOCAB[k % len(VOCAB)], "start": round(wt, 3), "end": round(wt + 0.28, 3)}
            )
            wt += 0.35
            k += 1
        words.extend(seg_words)
        segments.append(
            {
                "text": " ".join(w["text"] for w in seg_words),
                "start": round(t, 3),
                "end": round(seg_words[-1]["end"], 3),
            }
        )
        t = wt + 0.45
    cache = os.path.splitext(video_path)[0] + ".transcript.json"
    with open(cache, "w", encoding="utf-8") as fh:
        json.dump({"words": words, "segments": segments}, fh)
    return cache


def _probe(path, entries):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entries, "-of", "json", path],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def _run_cli(argv, workdir):
    """Run clip.main with scoring stubbed, from inside workdir."""
    import clip
    from pipeline import score as score_mod

    def fake_score(candidates):
        for i, c in enumerate(candidates):
            c.score = 10 - (i % 4)
            c.reason = "Opens on a hook and resolves cleanly."
            c.title = f"Candidate {i} Lands Hard"
        return candidates

    original = score_mod.score_candidates
    score_mod.score_candidates = fake_score
    clip.score.score_candidates = fake_score
    cwd = os.getcwd()
    try:
        os.chdir(workdir)
        return clip.main(argv)
    finally:
        os.chdir(cwd)
        score_mod.score_candidates = original
        clip.score.score_candidates = original


def test_dry_run_renders_nothing():
    if not HAVE_FFMPEG:
        print("    (skipped: ffmpeg not installed)")
        return
    with tempfile.TemporaryDirectory() as td:
        video = os.path.join(td, "talk.mp4")
        _make_video(video)
        _write_transcript_cache(video)
        assert _run_cli([video, "--dry-run", "--count", "3"], td) == 0
        assert not os.path.exists(os.path.join(td, "clips"))


def test_render_produces_vertical_clips_and_a_manifest():
    if not HAVE_FFMPEG:
        print("    (skipped: ffmpeg not installed)")
        return
    with tempfile.TemporaryDirectory() as td:
        video = os.path.join(td, "talk.mp4")
        _make_video(video)
        _write_transcript_cache(video)

        assert _run_cli([video, "--count", "2", "--min-score", "9"], td) == 0

        clips_dir = os.path.join(td, "clips")
        mp4s = sorted(f for f in os.listdir(clips_dir) if f.endswith(".mp4"))
        assert 1 <= len(mp4s) <= 2, mp4s
        assert all(f[:2].isdigit() and f[2] == "_" for f in mp4s), mp4s

        for name in mp4s:
            info = _probe(
                os.path.join(clips_dir, name),
                "stream=codec_name,width,height:format=duration",
            )
            video_stream = next(s for s in info["streams"] if "width" in s)
            audio_stream = next(s for s in info["streams"] if "width" not in s)
            assert (video_stream["width"], video_stream["height"]) == (1080, 1920)
            assert video_stream["codec_name"] == "h264"
            assert audio_stream["codec_name"] == "aac"
            assert 20.0 <= float(info["format"]["duration"]) <= 90.0

        manifest = json.load(open(os.path.join(clips_dir, "clips.json")))
        assert len(manifest) == len(mp4s)
        for record in manifest:
            assert set(record) == {
                "filename", "score", "reason", "title",
                "source_start", "source_end", "duration", "text",
            }
            assert record["filename"] in mp4s
            assert record["source_end"] > record["source_start"]
            assert abs(
                record["duration"] - (record["source_end"] - record["source_start"])
            ) < 0.01
            assert record["text"].strip()


def test_captions_are_burned_into_the_picture():
    """The rendered frame must differ from the same frame rendered caption-free."""
    if not HAVE_FFMPEG:
        print("    (skipped: ffmpeg not installed)")
        return
    from pipeline import render
    from pipeline.models import Candidate, Word

    with tempfile.TemporaryDirectory() as td:
        video = os.path.join(td, "talk.mp4")
        _make_video(video, seconds=12, width=320, height=180)

        words = [Word(text=w, start=1.0 + i * 0.5, end=1.4 + i * 0.5)
                 for i, w in enumerate(["clearly", "readable", "captions", "here"])]
        cand = Candidate(start=1.0, end=3.5, text="clearly readable captions here")
        cand.refined_start, cand.refined_end, cand.words = 1.0, 3.5, words

        with_caps = os.path.join(td, "with.mp4")
        render.render_clip(video, cand, with_caps, (320, 180))

        cand_blank = Candidate(start=1.0, end=3.5, text="")
        cand_blank.refined_start, cand_blank.refined_end, cand_blank.words = 1.0, 3.5, []
        without = os.path.join(td, "without.mp4")
        render.render_clip(video, cand_blank, without, (320, 180))

        # Pull the raw luma of the caption band from the same frame of each
        # render and compare pixel by pixel. Same source, same encode settings,
        # so the only thing that can differ is the burned-in text.
        band_h = 260
        band_y = int(render.OUT_H * render.CAPTION_HEIGHT_FRACTION) - band_h
        frames = []
        for src in (with_caps, without):
            out = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", "0.5", "-i", src,
                 "-frames:v", "1",
                 "-vf", f"crop={render.OUT_W}:{band_h}:0:{band_y},format=gray",
                 "-f", "rawvideo", "-"],
                capture_output=True, check=True,
            )
            frames.append(out.stdout)

        assert len(frames[0]) == len(frames[1]) == render.OUT_W * band_h
        differing = sum(1 for a, b in zip(frames[0], frames[1]) if a != b)
        assert differing > 1000, (
            f"only {differing} pixels differ in the caption band — "
            "captions do not appear to have been burned in"
        )


if __name__ == "__main__":  # pragma: no cover
    sys.exit("run via tests/run.py")
