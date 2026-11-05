"""Audio loudness measurement.

The claim being verified is audible sound, not a stream header, so these tests
build real media with FFmpeg in a temp directory: one silent AAC track (the exact
shape the engines used to report as a successful video with audio) and one with
actual tone.
"""

from __future__ import annotations

import subprocess

import pytest

from tezlify_studio.infrastructure.video.audio_probe import (
    AUDIBLE_MEAN_DB,
    probe_audio_loudness,
)


def _render(tmp_path, name: str, source: str, duration: float = 1.5) -> str:
    out = str(tmp_path / name)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", source,
         "-t", str(duration), "-c:a", "aac", "-ar", "44100", "-ac", "2", out],
        check=True,
    )
    return out


def test_digital_silence_is_reported_as_not_audible(tmp_path):
    path = _render(tmp_path, "silent.m4a", "anullsrc=channel_layout=stereo:sample_rate=44100")
    result = probe_audio_loudness(path)
    assert result.measured is True
    assert result.audible is False
    assert result.mean_db is not None and result.mean_db < AUDIBLE_MEAN_DB
    assert "silence" in result.reason


def test_real_audio_is_reported_as_audible(tmp_path):
    path = _render(tmp_path, "tone.m4a", "sine=frequency=440:sample_rate=44100")
    result = probe_audio_loudness(path)
    assert result.measured is True
    assert result.audible is True
    assert result.mean_db is not None and result.mean_db > -40
    assert result.max_db is not None and result.max_db >= result.mean_db


def test_a_file_without_an_audio_stream_is_not_claimed_audible(tmp_path):
    out = str(tmp_path / "video_only.mp4")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=64x64:d=1",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", out],
        check=True,
    )
    result = probe_audio_loudness(out)
    assert result.audible is False
    assert result.measured is False
    assert result.reason


def test_missing_file_fails_closed(tmp_path):
    result = probe_audio_loudness(str(tmp_path / "does-not-exist.mp4"))
    assert result.audible is False
    assert result.measured is False


def test_serialises_for_metadata(tmp_path):
    path = _render(tmp_path, "tone.m4a", "sine=frequency=300:sample_rate=44100")
    payload = probe_audio_loudness(path).to_dict()
    assert set(payload) == {"mean_db", "max_db", "audible", "measured", "reason"}


def test_loudness_threshold_is_a_single_documented_constant():
    # -91 dB (silence) and -21.8 dB (the Stage 5.4 speech reference) must fall on
    # opposite sides of it, which is the whole reason the constant exists.
    assert -91.0 < AUDIBLE_MEAN_DB < -21.8
