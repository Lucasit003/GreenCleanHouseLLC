"""Tests for the two external integrations, with each library stubbed.

faster-whisper's model weights and the Anthropic API are both out of reach in
CI (and in any offline checkout), so each library is replaced by a stub that
mirrors its real surface. What is under test here is our adapter code: the
whisper -> Word/Segment conversion plus caching, and the batching, parsing,
and retry behaviour around the scoring call.
"""

import json
import os
import sys
import tempfile
import types

from pipeline import score, transcribe
from pipeline.models import Candidate

# --------------------------------------------------------------- whisper stub


class _FWWord:
    """Mirrors faster_whisper.transcribe.Word."""

    def __init__(self, word, start, end):
        self.word, self.start, self.end, self.probability = word, start, end, 0.9


class _FWSegment:
    """Mirrors faster_whisper.transcribe.Segment."""

    def __init__(self, text, start, end, words):
        self.id, self.seek, self.tokens = 0, 0, []
        self.text, self.start, self.end, self.words = text, start, end, words


class _FakeWhisperModel:
    init_args = None
    last_kwargs = None

    def __init__(self, size, device=None, compute_type=None):
        type(self).init_args = (size, device, compute_type)

    def transcribe(self, audio_path, **kwargs):
        type(self).last_kwargs = kwargs
        segments = [
            # whitespace-padded tokens are what whisper actually emits
            _FWSegment(
                " Hello there friend.", 0.0, 1.4,
                [_FWWord(" Hello", 0.0, 0.4), _FWWord(" there", 0.45, 0.9),
                 _FWWord(" friend.", 0.95, 1.4)],
            ),
            # blank segment text and a blank word token
            _FWSegment("   ", 1.5, 1.6, [_FWWord("  ", 1.5, 1.6)]),
            _FWSegment(
                " Okay bye.", 2.0, 2.8,
                [_FWWord(" Okay", 2.0, 2.3), _FWWord(" bye.", 2.35, 2.8)],
            ),
            # words=None happens when a segment carries no word timings
            _FWSegment(" Hmm.", 3.0, 3.2, None),
        ]
        return iter(segments), types.SimpleNamespace(language="en", duration=3.2)


class _SilentWhisperModel(_FakeWhisperModel):
    def transcribe(self, audio_path, **kwargs):
        return iter([]), None


def _install_whisper(model_cls):
    module = types.ModuleType("faster_whisper")
    module.WhisperModel = model_cls
    sys.modules["faster_whisper"] = module


def test_whisper_enables_word_timestamps_and_forwards_model_size():
    _install_whisper(_FakeWhisperModel)
    with tempfile.TemporaryDirectory() as td:
        video = os.path.join(td, "source.mp4")
        open(video, "wb").close()
        transcribe.transcribe(video, "/tmp/fake.wav", "small")
    assert _FakeWhisperModel.last_kwargs.get("word_timestamps") is True
    assert _FakeWhisperModel.init_args[0] == "small"


def test_whisper_strips_tokens_and_drops_blanks():
    _install_whisper(_FakeWhisperModel)
    with tempfile.TemporaryDirectory() as td:
        video = os.path.join(td, "source.mp4")
        open(video, "wb").close()
        words, segments = transcribe.transcribe(video, "/tmp/fake.wav", "base")
    assert [w.text for w in words] == ["Hello", "there", "friend.", "Okay", "bye."]
    assert [s.text for s in segments] == ["Hello there friend.", "Okay bye.", "Hmm."]
    assert all(w.end > w.start for w in words)


def test_transcript_cache_format_and_roundtrip():
    _install_whisper(_FakeWhisperModel)
    with tempfile.TemporaryDirectory() as td:
        video = os.path.join(td, "my talk.mp4")  # a space in the name on purpose
        open(video, "wb").close()
        words, segments = transcribe.transcribe(video, "/tmp/fake.wav", "base")

        cache = transcribe.cache_path_for(video)
        assert cache == os.path.join(td, "my talk.transcript.json")
        raw = json.load(open(cache))
        assert set(raw) == {"words", "segments"}
        assert set(raw["words"][0]) == {"text", "start", "end"}
        assert set(raw["segments"][0]) == {"text", "start", "end"}

        w2, s2 = transcribe.load_cache(cache)
        assert [w.text for w in w2] == [w.text for w in words]
        assert [(s.start, s.end) for s in s2] == [(s.start, s.end) for s in segments]


def test_cache_is_invalidated_when_the_source_changes():
    _install_whisper(_FakeWhisperModel)
    with tempfile.TemporaryDirectory() as td:
        video = os.path.join(td, "source.mp4")
        open(video, "wb").close()
        transcribe.transcribe(video, "/tmp/fake.wav", "base")
        cache = transcribe.cache_path_for(video)

        assert transcribe.cache_is_fresh(video, cache)
        os.utime(video, (os.path.getmtime(cache) + 10,) * 2)
        assert not transcribe.cache_is_fresh(video, cache)
        assert not transcribe.cache_is_fresh(video, os.path.join(td, "absent.json"))


def test_silent_input_fails_loudly():
    _install_whisper(_SilentWhisperModel)
    try:
        transcribe.transcribe("/tmp/x.mp4", "/tmp/fake.wav", "base")
    except SystemExit as exc:
        assert "no words" in str(exc)
        return
    raise AssertionError("silence should raise SystemExit")


def test_model_load_failure_is_actionable():
    class Exploding(_FakeWhisperModel):
        def __init__(self, *a, **k):
            raise OSError("403 Forbidden")

    _install_whisper(Exploding)
    try:
        transcribe.transcribe("/tmp/x.mp4", "/tmp/fake.wav", "tiny")
    except SystemExit as exc:
        message = str(exc)
        assert "huggingface.co" in message  # names the likely cause
        assert "--model" in message  # offers the offline route
        return
    raise AssertionError("a model load failure should raise SystemExit")


# -------------------------------------------------------------- anthropic stub

_calls = []


class _FakeAPIError(Exception):
    pass


class _FakeBlock:
    def __init__(self, text):
        self.type, self.text = "text", text


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]


class _FakeClient:
    def __init__(self, script):
        outer = self

        class Messages:
            def create(self, **kwargs):
                _calls.append(kwargs)
                behaviour = outer.script(len(_calls) - 1, kwargs)
                if isinstance(behaviour, Exception):
                    raise behaviour
                return _FakeResponse(behaviour)

        self.script = script
        self.messages = Messages()


def _install_anthropic(script):
    _calls.clear()
    module = types.ModuleType("anthropic")
    module.Anthropic = lambda api_key=None: _FakeClient(script)
    module.APIError = _FakeAPIError
    sys.modules["anthropic"] = module
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"


def _candidates(n):
    return [
        Candidate(start=i * 40.0, end=i * 40.0 + 35.0, text=f"transcript {i}")
        for i in range(n)
    ]


def _batch_indexes(kwargs):
    import re

    return [int(x) for x in re.findall(r"--- candidate (\d+) ---",
                                       kwargs["messages"][0]["content"])]


def _ok(_i, kwargs):
    return json.dumps(
        [
            {"index": i, "score": 7, "reason": f"r{i}", "title": f"Title {i}"}
            for i in _batch_indexes(kwargs)
        ]
    )


def test_candidates_are_sent_in_batches_of_ten():
    _install_anthropic(_ok)
    scored = score.score_candidates(_candidates(25))
    sizes = [c["messages"][0]["content"].count("--- candidate ") for c in _calls]
    assert sizes == [10, 10, 5], sizes
    assert len(scored) == 25


def test_request_uses_the_configured_model_and_editor_system_prompt():
    _install_anthropic(_ok)
    score.score_candidates(_candidates(2))
    assert _calls[0]["model"] == score.MODEL
    system = _calls[0]["system"]
    assert "short-form content editor" in system
    assert "hook in the first 3 seconds" in system
    assert "JSON array" in system


def test_missing_api_key_is_reported_clearly():
    _install_anthropic(_ok)
    del os.environ["ANTHROPIC_API_KEY"]
    try:
        score.score_candidates(_candidates(1))
    except SystemExit as exc:
        assert ".env" in str(exc) and "ANTHROPIC_API_KEY" in str(exc)
        return
    finally:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
    raise AssertionError("a missing key should raise SystemExit")


def test_markdown_fences_are_stripped_defensively():
    _install_anthropic(lambda i, kw: "```json\n" + _ok(i, kw) + "\n```")
    assert len(score.score_candidates(_candidates(3))) == 3
    assert len(_calls) == 1


def test_unparseable_response_is_retried_once():
    _install_anthropic(lambda i, kw: "not json" if i == 0 else _ok(i, kw))
    scored = score.score_candidates(_candidates(4))
    assert len(_calls) == 2
    assert len(scored) == 4


def test_batch_failing_twice_is_skipped_and_the_run_continues():
    _install_anthropic(lambda i, kw: "not json" if i < 2 else _ok(i, kw))
    scored = score.score_candidates(_candidates(14))  # two batches
    assert len(_calls) == 3  # 2 attempts on batch 1, 1 on batch 2
    assert len(scored) == 4  # only the second batch survives


def test_api_errors_are_retried_then_skipped():
    _install_anthropic(lambda i, kw: _FakeAPIError("503 overloaded"))
    assert score.score_candidates(_candidates(5)) == []
    assert len(_calls) == 2


def test_malformed_items_are_skipped_individually():
    _install_anthropic(
        lambda i, kw: json.dumps(
            [
                {"index": 0, "score": 99, "reason": "clamp", "title": "Clamp Me"},
                {"index": 1, "score": "not a number"},
                {"index": 7, "score": 5, "reason": "unknown index", "title": "Ghost"},
                {"score": 5, "title": "no index at all"},
                {"index": 2, "score": 4, "title": "Missing Reason"},
            ]
        )
    )
    cands = _candidates(3)
    score.score_candidates(cands)
    assert cands[0].score == 10  # clamped from 99
    assert cands[1].score == 0  # invalid item never applied
    assert cands[2].score == 4 and cands[2].reason == ""


def test_no_candidates_makes_no_api_calls():
    _install_anthropic(_ok)
    assert score.score_candidates([]) == []
    assert _calls == []
