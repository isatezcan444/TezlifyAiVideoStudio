"""Measure whether a finished video actually contains sound.

`has_audio` only ever meant "an AAC stream exists", and the engines deliberately
synthesise a silent AAC track when there is nothing to mix, so every render of a
project without dialogue audio reported success with a video that plays back
silent. Stage 5.4.1 caught that on a real file: mean and peak volume both
-91.0 dB.

This measures loudness with FFmpeg's own `volumedetect` filter rather than
trusting metadata, because the claim being verified is audible sound, not a
stream header.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Optional

# Anything quieter than this is effectively silence for a viewer. Digital
# silence measured -91.0 dB on the reference file; normal speech sits around
# -20 dB, so the threshold has a wide margin on both sides.
AUDIBLE_MEAN_DB = -60.0

_MEAN_RE = re.compile(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB")
_MAX_RE = re.compile(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB")


@dataclass(frozen=True)
class AudioLoudness:
    mean_db: Optional[float]
    max_db: Optional[float]
    audible: bool
    measured: bool
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "mean_db": self.mean_db,
            "max_db": self.max_db,
            "audible": self.audible,
            "measured": self.measured,
            "reason": self.reason,
        }


def probe_audio_loudness(path: str, ffmpeg: str = "ffmpeg") -> AudioLoudness:
    """Decode the audio stream and report its real level."""
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", path, "-map", "0:a:0",
             "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return AudioLoudness(None, None, False, False, f"ffmpeg error: {exc}")

    blob = proc.stderr or ""
    mean_match, max_match = _MEAN_RE.search(blob), _MAX_RE.search(blob)
    if mean_match is None:
        reason = "no audio stream" if "does not contain any stream" in blob or "Stream map" in blob \
            else "volumedetect produced no measurement"
        return AudioLoudness(None, None, False, False, reason)

    mean_db = float(mean_match.group(1))
    max_db = float(max_match.group(1)) if max_match else None
    return AudioLoudness(
        mean_db=mean_db,
        max_db=max_db,
        audible=mean_db > AUDIBLE_MEAN_DB,
        measured=True,
        reason="" if mean_db > AUDIBLE_MEAN_DB else f"mean volume {mean_db} dB is silence",
    )
