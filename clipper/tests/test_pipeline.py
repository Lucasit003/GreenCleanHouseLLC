"""Pure-logic tests: windowing, dedup, cut refinement, crop math, captions.

No ffmpeg, no network, no API key.
"""

from pipeline import cut, render, score
from pipeline.models import Candidate, Segment, Word


def _synthetic_transcript(seconds=600.0):
    """3s segments of 5 words each, evenly spaced."""
    segments, words = [], []
    t, i = 0.0, 0
    while t < seconds:
        seg_words = []
        wt = t
        for _ in range(5):
            w = Word(text=f"w{i}", start=wt, end=wt + 0.5)
            seg_words.append(w)
            words.append(w)
            wt += 0.6
            i += 1
        segments.append(
            Segment(text=" ".join(w.text for w in seg_words), start=t, end=t + 2.9)
        )
        t += 3.0
    return segments, words


def test_windows_respect_duration_bounds():
    segments, words = _synthetic_transcript()
    cands = score.build_candidates(segments, words)
    assert cands
    for c in cands:
        assert score.HARD_MIN <= c.duration <= score.HARD_MAX
        assert 30.0 <= c.duration <= 75.0


def test_windows_snap_to_segment_boundaries():
    segments, words = _synthetic_transcript()
    starts = {round(s.start, 3) for s in segments}
    ends = {round(s.end, 3) for s in segments}
    for c in score.build_candidates(segments, words):
        assert round(c.start, 3) in starts
        assert round(c.end, 3) in ends


def test_windows_overlap_roughly_half():
    segments, words = _synthetic_transcript()
    starts = sorted({c.start for c in score.build_candidates(segments, words)})
    steps = [b - a for a, b in zip(starts, starts[1:])]
    # windows are ~30s; start points must advance by roughly half that
    assert max(steps) <= 20.0


def test_empty_transcript_yields_no_candidates():
    assert score.build_candidates([], []) == []


def test_dedup_drops_heavy_overlap():
    segments, words = _synthetic_transcript()
    cands = score.build_candidates(segments, words)
    for n, c in enumerate(cands):
        c.score = 10 - (n % 5)
    kept = score.deduplicate(cands)
    assert len(kept) < len(cands)
    for i in range(len(kept)):
        for j in range(i + 1, len(kept)):
            assert score._overlap_fraction(kept[i], kept[j]) <= 0.30


def test_dedup_prefers_higher_scores():
    a = Candidate(start=0, end=40, text="a")
    b = Candidate(start=5, end=45, text="b")  # overlaps a heavily
    a.score, b.score = 6, 9
    kept = score.deduplicate([a, b])
    assert [c.score for c in kept] == [9]


_GAPPED = [
    Word("hello", 10.00, 10.40),
    Word("there", 10.45, 10.90),  # tight against the previous word
    Word("friend", 11.90, 12.40),  # 1.0s gap before
    Word("okay", 12.50, 12.90),
    Word("bye", 14.00, 14.50),  # 1.1s gap before
]


def test_refine_cuts_inside_a_pause():
    c = Candidate(start=11.5, end=13.5, text="")
    assert cut.refine(c, _GAPPED, 100.0)
    assert [w.text for w in c.words] == ["friend", "okay"]
    assert abs(c.cut_start - (10.90 + 1.0 / 2)) < 1e-6
    assert abs(c.cut_end - (12.90 + 1.1 / 2)) < 1e-6


def test_refine_never_splits_a_word():
    for start, end in [(11.5, 13.5), (10.4, 11.0), (0.0, 14.6), (12.0, 12.6)]:
        c = Candidate(start=start, end=end, text="")
        if not cut.refine(c, _GAPPED, 100.0):
            continue
        assert c.cut_start <= c.words[0].start
        assert c.cut_end >= c.words[-1].end
        for w in _GAPPED:
            straddles_start = w.start < c.cut_start < w.end
            straddles_end = w.start < c.cut_end < w.end
            assert not straddles_start and not straddles_end


def test_refine_respects_tight_neighbours():
    c = Candidate(start=10.4, end=11.0, text="")
    assert cut.refine(c, _GAPPED, 100.0)
    assert c.words[0].text == "there"
    assert c.cut_start >= _GAPPED[0].end  # must not run into "hello"


def test_refine_clamps_to_video_bounds():
    c = Candidate(start=0.0, end=11.0, text="")
    assert cut.refine(c, _GAPPED, 10.95)
    assert c.cut_start >= 0.0
    assert c.cut_end <= 10.95


def test_refine_rejects_windows_with_no_whole_word():
    c = Candidate(start=10.5, end=10.6, text="")
    assert not cut.refine(c, _GAPPED, 100.0)
    assert not cut.refine(Candidate(start=0, end=5, text=""), [], 100.0)


def test_refine_sets_text_from_kept_words():
    c = Candidate(start=11.5, end=13.5, text="stale text")
    assert cut.refine(c, _GAPPED, 100.0)
    assert c.text == "friend okay"


def test_crop_is_nine_by_sixteen_and_inside_the_frame():
    for w, h in [(1920, 1080), (1080, 1080), (720, 1280), (640, 480), (3840, 2160)]:
        cw, ch, x, y = render.crop_rect(w, h)
        assert cw <= w and ch <= h
        assert cw % 2 == 0 and ch % 2 == 0
        assert abs(cw / ch - 9 / 16) < 0.01
        assert x + cw <= w and y + ch <= h


def test_crop_is_centered():
    cw, _ch, x, _y = render.crop_rect(1920, 1080)
    assert x == (1920 - cw) // 2


def test_captions_show_two_words_at_a_time():
    ass = render.build_ass(_GAPPED, clip_start=10.0, clip_duration=5.0)
    lines = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]
    assert len(lines) == 3  # 5 words -> 2 + 2 + 1
    assert lines[0].endswith("hello there")
    assert lines[-1].endswith("bye")


def test_caption_times_are_relative_to_the_clip():
    ass = render.build_ass(_GAPPED, clip_start=10.0, clip_duration=5.0)
    first = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")][0]
    assert first.startswith("Dialogue: 0,0:00:00.00,0:00:00.90,Caption")


def test_caption_times_stay_inside_the_clip():
    ass = render.build_ass(_GAPPED, clip_start=10.0, clip_duration=2.0)
    for line in [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]:
        _, start, end = line.split(",")[:3]
        assert end <= "0:00:02.00"
        assert start < end


def test_caption_style_is_portable_and_positioned():
    ass = render.build_ass(_GAPPED, 10.0, 5.0)
    assert f"Style: Caption,{render.CAPTION_FONT}," in ass
    # bold (-1), white primary, black outline, alignment 2, margin from 60% height
    assert "&H00FFFFFF" in ass and "&H00000000" in ass
    expected_margin = int(render.OUT_H * (1 - render.CAPTION_HEIGHT_FRACTION))
    assert f",2,60,60,{expected_margin},1" in ass
    assert f"PlayResX: {render.OUT_W}" in ass and f"PlayResY: {render.OUT_H}" in ass


def test_ass_escaping_neutralises_override_braces():
    assert render._ass_escape("a{b}c") == "a(b)c"
    assert render._ass_escape("back\\slash") == "back\\\\slash"


def test_empty_word_list_still_produces_valid_ass():
    ass = render.build_ass([], 0.0, 5.0)
    assert "[Events]" in ass
    assert not [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]


def test_filenames_are_score_prefixed_slugs():
    c = Candidate(start=0, end=30, text="")
    c.score, c.title = 8, "The Thing He Said!"
    assert render.clip_filename(c, 1) == "08_the-thing-he-said.mp4"
    c.score, c.title = 10, ""
    assert render.clip_filename(c, 3) == "10_clip-03.mp4"


def test_slugify_handles_punctuation_and_length():
    assert render.slugify("Hello, World -- Again!") == "hello-world-again"
    assert render.slugify("   ") == "clip"
    assert len(render.slugify("x" * 200)) <= 60


def test_response_parsing_strips_fences_and_rejects_non_arrays():
    assert score._parse_batch_response('```json\n[{"index":0}]\n```') == [{"index": 0}]
    assert score._parse_batch_response('```\n[{"index":0}]\n```') == [{"index": 0}]
    assert score._parse_batch_response(' [{"index":1}] ') == [{"index": 1}]
    for bad in ['{"index": 0}', "not json at all"]:
        try:
            score._parse_batch_response(bad)
        except (ValueError, __import__("json").JSONDecodeError):
            continue
        raise AssertionError(f"should have rejected: {bad!r}")


def test_clip_record_serialises_every_documented_field():
    c = Candidate(start=1.0, end=31.0, text="hello")
    c.score, c.reason, c.title = 9, "hooks fast", "Great Clip"
    c.refined_start, c.refined_end = 1.2345, 30.6789
    record = render.to_clip_record(c, "09_great-clip.mp4").to_dict()
    assert set(record) == {
        "filename", "score", "reason", "title",
        "source_start", "source_end", "duration", "text",
    }
    assert record["source_start"] == 1.234 or record["source_start"] == 1.235
    assert abs(record["duration"] - (30.6789 - 1.2345)) < 0.01
