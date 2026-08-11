# Long-Form Video Clipper

Extracts short vertical (9:16) clips with burned-in captions from a long video —
podcasts, interviews, talking-head recordings up to a couple of hours. Output is a
folder of mp4s ready to post to TikTok, Reels, or Shorts.

Local command-line tool. No server, no accounts, no database — JSON files on disk
are the storage layer.

## Setup

Requires Python 3.11+ and ffmpeg.

```bash
# 1. ffmpeg (external binaries — checked on startup)
brew install ffmpeg              # macOS
sudo apt-get install ffmpeg      # Debian/Ubuntu

# 2. Python dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. API key
cp .env.example .env
# then edit .env and paste your key from console.anthropic.com
```

## Usage

```bash
python clip.py <video_path> [--count 8] [--min-score 6] [--model base] [--dry-run]
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--count` | 8 | Max clips to produce |
| `--min-score` | 6 | Discard candidates scoring below this |
| `--model` | `base` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large-v3`), or a path to a local model directory |
| `--dry-run` | off | Transcribe and score, print the ranked list, render nothing |

Start with `--dry-run`. It gives you the ranked candidate list with timestamps and
reasons in seconds, so you can judge clip selection without waiting on encoding:

```bash
python clip.py podcast.mp4 --dry-run
python clip.py podcast.mp4 --dry-run --min-score 7   # re-runs off the cache, instant
python clip.py podcast.mp4 --count 5                  # happy with the list? render
```

## Output

```
clips/
  09_the-thing-he-said.mp4
  08_why-nobody-ships.mp4
  clips.json
```

Filenames are `<score>_<title-slug>.mp4`. `clips.json` is an array of objects with
`filename`, `score`, `reason`, `title`, `source_start`, `source_end`, `duration`,
and the clip's transcript `text`.

## Tests

```bash
python tests/run.py              # everything
python tests/run.py pipeline     # just the pure-logic tests
```

No test runner to install — plain asserts and a small dispatcher. `pytest tests/`
also works if you happen to have it.

`test_pipeline.py` covers windowing, dedup, cut refinement, crop math, and caption
generation. `test_integrations.py` stubs `faster-whisper` and the Anthropic client
to exercise the adapter code — transcript conversion and caching, batching,
fence-stripping, retry-then-skip — without weights or an API key.
`test_render.py` shells out to real ffmpeg to render a synthetic clip and checks
the output is 1080×1920 h264/AAC with captions actually burned into the pixels;
it skips itself if ffmpeg is missing.

## How it works

1. **Audio extraction** — ffmpeg streams a 16kHz mono WAV to a temp file, deleted
   when the run finishes. The video is never loaded into memory.
2. **Transcription** — `faster-whisper` with word-level timestamps. The result is
   cached as `<videoname>.transcript.json` beside the source video. Later runs skip
   this stage entirely unless the source file is newer than the cache. This is the
   slow step, and you will re-run the tool many times while tuning.
3. **Candidates and scoring** — sliding windows of 30–75s snapped to sentence
   boundaries, overlapping ~50%. Windows go to Claude in batches of 10 for a 1–10
   score, a one-line reason, and a title. Overlapping winners are then reduced
   greedily by score, dropping anything overlapping a pick by more than 30%.
4. **Cut refinement** — boundaries snap to word edges (never mid-word) with 150ms
   of lead-in and 300ms of tail. Where a pause of 200ms or more sits next to a
   boundary, the cut lands inside that pause.
5. **Render** — one ffmpeg call per clip: trim, center-crop to 9:16, scale to
   1080×1920, burn captions from a generated ASS file (two words at a time, bold
   white on black outline, at 60% of frame height). libx264 `-preset fast -crf 23`,
   AAC 128k.

## Notes

- The first run downloads the Whisper model weights from huggingface.co; later
  runs reuse the cached copy. To run somewhere without that access, fetch a
  faster-whisper model once on a connected machine and point `--model` at the
  directory: `--model /path/to/faster-whisper-base`.
- Larger `--model` values are slower but noticeably better on crosstalk and
  accents. `base` is a good default for clean single-speaker audio.
- Reframing is a plain center crop. There is no face tracking or speaker
  detection — if the speaker sits far off-center in the source, expect to crop
  them out.
