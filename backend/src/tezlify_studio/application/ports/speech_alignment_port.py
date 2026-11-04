from abc import ABC, abstractmethod
from typing import Dict, List

from tezlify_studio.domain.value_objects.speech_alignment import (
    AlignmentRequest,
    DialogueAlignment,
)


class SpeechAlignmentPort(ABC):
    """Turns spoken lines and their real audio files into timed sound segments.

    Implementations must only return intervals measured from the audio. A provider
    that cannot align raises instead of guessing, because the renderer treats "no
    alignment" and "fake alignment" very differently — the first falls back to the
    legacy mouth animation with an explicit label, the second would be a lie.

    The API is batch-oriented on purpose: the acoustic model costs seconds and over
    a gigabyte of RAM to load, so aligning one dialogue at a time would pay that on
    every line.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """True only when real alignment can actually run on this machine."""
        pass

    @abstractmethod
    def describe(self) -> str:
        """Short human-readable identity of the engine, for logs and the UI."""
        pass

    @abstractmethod
    def align(self, requests: List[AlignmentRequest]) -> Dict[str, DialogueAlignment]:
        """Align every request, returning results keyed by ``dialogue_id``.

        A dialogue the provider could not align is simply absent from the result;
        callers fall back for those and must report that they did.
        """
        pass
