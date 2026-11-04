"""Stage 5.4 — alignment provider and lip-sync resolver behaviour.

These exercise the subprocess contract, the cache and the fallback rules without
requiring the isolated ML environment: the worker is replaced by a stub script
that speaks the same protocol.
"""

import json
import os
import subprocess
import sys

import pytest

from tezlify_studio.application.services.lip_sync_resolver import LipSyncResolver
from tezlify_studio.domain.enums.studio_status import (
    AlignmentSource,
    CameraAngle,
    CameraMovement,
    CharacterExpression,
    CharacterPose,
    MouthViseme,
)
from tezlify_studio.domain.value_objects.scene_graph import (
    CharacterPlacement,
    SceneBackground,
    SceneCamera,
    SceneCharacter,
    SceneDialogue,
    SceneGraph,
    SceneResolution,
    StudioScene,
)
from tezlify_studio.domain.value_objects.speech_alignment import (
    AlignmentRequest,
    DialogueAlignment,
    VisemeSegment,
)
from tezlify_studio.infrastructure.alignment import ctc_forced_alignment_impl as impl_module
from tezlify_studio.infrastructure.alignment.ctc_forced_alignment_impl import (
    CTCForcedAlignmentImpl,
)

STUB_WORKER = '''#!/usr/bin/env python3
import json, sys
request = json.load(open(sys.argv[1], encoding="utf-8"))
alignments = {}
errors = {}
for item in request["requests"]:
    if item["text"].startswith("FAIL"):
        errors[item["dialogue_id"]] = "stub: refused"
        continue
    alignments[item["dialogue_id"]] = {
        "segments": [
            {"phoneme": "m", "start_time": 0.02, "end_time": 0.10, "confidence": 0.4},
            {"phoneme": "a", "start_time": 0.10, "end_time": 0.30, "confidence": 0.6},
        ],
        "diagnostics": {"audio_duration_seconds": item["audio_duration_seconds"]},
        "elapsed_seconds": 0.1,
    }
json.dump({"ok": bool(alignments), "engine": "stub", "model_id": request["model_id"],
           "model_load_seconds": 0.5, "alignments": alignments, "errors": errors},
          open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
sys.exit(0 if alignments else 1)
'''


@pytest.fixture(scope="module")
def speech_file(tmp_path_factory):
    """A real short MP3, because the resolver measures duration with ffprobe."""
    directory = tmp_path_factory.mktemp("lipsync_audio")
    path = directory / "speech.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=0.6", "-c:a", "libmp3lame", "-b:a", "64k", str(path)],
        check=True,
    )
    return str(path)


@pytest.fixture
def stub_provider(tmp_path, speech_file):
    """A provider whose 'venv' is a stub script speaking the real protocol."""
    worker = tmp_path / "stub_worker.py"
    worker.write_text(STUB_WORKER, encoding="utf-8")

    original = impl_module.WORKER_SCRIPT
    impl_module.WORKER_SCRIPT = str(worker)
    provider = CTCForcedAlignmentImpl(
        python_executable=sys.executable,
        model_id="stub-model",
        cache_dir=str(tmp_path / "cache"),
        model_cache_dir=None,
        timeout_seconds=120,
    )
    yield provider, speech_file
    impl_module.WORKER_SCRIPT = original


def request_for(audio_file, text="Merhaba", dialogue_id="d1", speaker="char_ali"):
    return AlignmentRequest(
        dialogue_id=dialogue_id, speaker_id=speaker, text=text,
        audio_file=audio_file, audio_duration_seconds=2.0,
    )


def alignment_for(speaker, start=0.02, end=0.30):
    return DialogueAlignment(
        dialogue_id="x", speaker_id=speaker, text="Merhaba",
        audio_file="x", audio_duration_seconds=2.0,
        phonemes=[],
        visemes=[
            VisemeSegment(start_time=start, end_time=0.10, viseme=MouthViseme.CLOSED,
                          phoneme="m", speaker_id=speaker, confidence=0.5,
                          source=AlignmentSource.CTC_FORCED),
            VisemeSegment(start_time=0.10, end_time=end, viseme=MouthViseme.OPEN,
                          phoneme="a", speaker_id=speaker, confidence=0.5,
                          source=AlignmentSource.CTC_FORCED),
        ],
    )


class PerSpeakerProvider:
    """Returns one measured alignment per request, and records what it was asked."""

    def __init__(self, results_factory=None, available=True):
        self.available = available
        self.factory = results_factory or (lambda r: alignment_for(r.speaker_id))
        self.seen_requests = []

    def is_available(self):
        return self.available

    def describe(self):
        return "stub alignment engine"

    def align(self, requests):
        self.seen_requests.extend(requests)
        if not self.available:
            return {}
        return {r.dialogue_id: self.factory(r) for r in requests}


def build_graph(audio_files):
    """One scene, two speakers, dialogue audio wired the way the TTS step does."""
    return SceneGraph(
        project_id="proj_lipsync",
        title="Lip Sync Testi",
        resolution=SceneResolution(width=1080, height=1920, aspect_ratio="9:16", fps=30),
        characters=[
            SceneCharacter(id="char_ali", name="Ali"),
            SceneCharacter(id="char_ayse", name="Ayşe"),
        ],
        scenes=[
            StudioScene(
                scene_id="scene_01",
                duration_seconds=4.0,
                background=SceneBackground(asset_id="bg_modern_cafe"),
                camera=SceneCamera(angle=CameraAngle.TWO_SHOT, movement=CameraMovement.STATIC),
                character_placements=[
                    CharacterPlacement(character_id="char_ali", position=[-0.55, 0.0, 0.0],
                                       pose=CharacterPose.STANDING,
                                       expression=CharacterExpression.CHEERFUL),
                    CharacterPlacement(character_id="char_ayse", position=[0.55, 0.0, 0.0],
                                       pose=CharacterPose.STANDING,
                                       expression=CharacterExpression.CHEERFUL),
                ],
                dialogues=[
                    SceneDialogue(character_id="char_ali", start_time=0.4, end_time=1.8,
                                  text="Merhaba", audio_file=audio_files[0]),
                    SceneDialogue(character_id="char_ayse", start_time=2.0, end_time=3.6,
                                  text="Merhaba", audio_file=audio_files[1]),
                ],
            )
        ],
    )


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

def test_provider_reports_availability_from_the_isolated_environment(tmp_path):
    assert CTCForcedAlignmentImpl(
        python_executable="", model_id="m", cache_dir=str(tmp_path),
    ).is_available() is False

    present = CTCForcedAlignmentImpl(
        python_executable=sys.executable, model_id="m", cache_dir=str(tmp_path),
    )
    # Availability is a path check; the real worker ships in the repo tree.
    assert present.is_available() is True


def test_align_returns_measured_visemes_from_the_worker(stub_provider):
    provider, audio = stub_provider
    results = provider.align([request_for(audio)])

    assert set(results) == {"d1"}
    alignment = results["d1"]
    assert alignment.is_real is True
    assert alignment.source == AlignmentSource.CTC_FORCED
    assert [p.phoneme for p in alignment.phonemes] == ["m", "a"]
    assert [v.viseme.value for v in alignment.visemes] == ["CLOSED", "OPEN"]
    assert alignment.visemes[0].start_time == pytest.approx(0.02)
    assert alignment.visemes[-1].end_time == pytest.approx(0.30)
    assert alignment.fingerprint


def test_align_without_provider_environment_returns_empty(tmp_path, speech_file):
    provider = CTCForcedAlignmentImpl(
        python_executable="", model_id="m", cache_dir=str(tmp_path),
    )
    assert provider.align([request_for(speech_file)]) == {}


def test_unalignable_dialogue_is_absent_rather_than_guessed(stub_provider):
    provider, audio = stub_provider
    results = provider.align([
        request_for(audio, text="Merhaba", dialogue_id="ok"),
        request_for(audio, text="FAIL me", dialogue_id="bad"),
    ])
    assert set(results) == {"ok"}


def test_second_call_is_served_from_cache_without_the_worker(stub_provider, tmp_path, monkeypatch):
    provider, audio = stub_provider
    first = provider.align([request_for(audio)])
    assert first

    cache_files = os.listdir(str(tmp_path / "cache"))
    assert len(cache_files) == 1, cache_files

    # Break the worker: a cache hit must not need it.
    monkeypatch.setattr(impl_module, "WORKER_SCRIPT", str(tmp_path / "gone.py"))
    second = provider.align([request_for(audio)])
    assert second["d1"].model_dump() == first["d1"].model_dump()


def test_cache_invalidates_when_the_text_changes(stub_provider, monkeypatch):
    provider, audio = stub_provider
    provider.align([request_for(audio, text="Merhaba")])

    calls = []
    original = provider._run_worker

    def spy(requests):
        calls.append(len(requests))
        return original(requests)

    monkeypatch.setattr(provider, "_run_worker", spy)
    provider.align([request_for(audio, text="Merhaba!")])
    assert calls == [1], "a different transcript must not be served from cache"

    calls.clear()
    provider.align([request_for(audio, text="Merhaba!")])
    assert calls == [], "the same transcript must be served from cache"


def test_corrupt_cache_entry_is_ignored(stub_provider):
    provider, audio = stub_provider
    request = request_for(audio)
    os.makedirs(provider.cache_dir, exist_ok=True)
    path = os.path.join(provider.cache_dir, f"{request.cache_key(provider.model_id)}.json")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{not json")
    assert provider._load_cache(request) is None
    assert provider.align([request]), "provider must recover by calling the worker"


def test_worker_protocol_sends_absolute_paths(stub_provider):
    provider, audio = stub_provider
    captured = {}
    real_run = subprocess.run

    def spy(command, **kwargs):
        # The request file lives in a TemporaryDirectory that is gone by the time
        # align() returns, so read the payload here rather than after.
        with open(command[2], encoding="utf-8") as handle:
            captured["payload"] = json.load(handle)
        return real_run(command, **kwargs)

    provider_module_subprocess = impl_module.subprocess
    original_run = provider_module_subprocess.run
    provider_module_subprocess.run = spy
    try:
        provider.align([request_for(audio)])
    finally:
        provider_module_subprocess.run = original_run

    payload = captured["payload"]
    assert payload["model_id"] == "stub-model"
    sent = payload["requests"][0]
    assert os.path.isabs(sent["audio_file"]), "relative paths would miss in the subprocess"
    assert os.path.isfile(sent["audio_file"])
    assert sent["audio_duration_seconds"] == pytest.approx(2.0)


def test_worker_failure_degrades_to_no_results(tmp_path, speech_file):
    worker = tmp_path / "broken.py"
    worker.write_text("import sys; sys.exit(9)\n", encoding="utf-8")
    original = impl_module.WORKER_SCRIPT
    impl_module.WORKER_SCRIPT = str(worker)
    try:
        provider = CTCForcedAlignmentImpl(
            python_executable=sys.executable, model_id="m", cache_dir=str(tmp_path / "cache"),
        )
        assert provider.align([request_for(speech_file)]) == {}
    finally:
        impl_module.WORKER_SCRIPT = original


def test_unreadable_worker_response_is_not_fatal(tmp_path, speech_file):
    worker = tmp_path / "junk.py"
    worker.write_text("import sys\nopen(sys.argv[2],'w').write('not json at all')\n", encoding="utf-8")
    original = impl_module.WORKER_SCRIPT
    impl_module.WORKER_SCRIPT = str(worker)
    try:
        provider = CTCForcedAlignmentImpl(
            python_executable=sys.executable, model_id="m", cache_dir=str(tmp_path / "cache"),
        )
        assert provider.align([request_for(speech_file)]) == {}
    finally:
        impl_module.WORKER_SCRIPT = original


def test_empty_request_batch_never_launches_a_worker(stub_provider):
    provider, _ = stub_provider
    assert provider.align([]) == {}


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

def test_resolver_writes_measured_visemes_into_the_scene_graph(speech_file):
    graph = build_graph([speech_file, speech_file])
    provider = PerSpeakerProvider()

    resolved, report = LipSyncResolver(provider).resolve(graph)

    assert report.dialogues_total == 2
    assert report.dialogues_with_audio == 2
    assert report.dialogues_aligned == 2
    assert report.dialogues_fallback == 0
    assert report.uses_real_alignment is True
    assert report.reasons == {}
    assert report.mean_confidence == pytest.approx(0.5)

    for scene in resolved.scenes:
        for dialogue in scene.dialogues:
            assert len(dialogue.visemes) == 2
            assert all(v.is_measured for v in dialogue.visemes)
            assert dialogue.visemes[0].viseme == MouthViseme.CLOSED
            assert dialogue.visemes[0].end_time is not None


def test_resolver_leaves_graph_untouched_when_provider_unavailable(speech_file):
    graph = build_graph([speech_file, speech_file])
    before = [
        [v.model_dump() for d in scene.dialogues for v in d.visemes]
        for scene in graph.scenes
    ]

    resolved, report = LipSyncResolver(PerSpeakerProvider(available=False)).resolve(graph)

    assert report.enabled is False
    assert report.dialogues_aligned == 0
    assert report.uses_real_alignment is False
    assert "*" in report.reasons
    after = [
        [v.model_dump() for d in scene.dialogues for v in d.visemes]
        for scene in resolved.scenes
    ]
    assert after == before


def test_resolver_reports_fallback_when_nothing_aligned(speech_file):
    graph = build_graph([speech_file, speech_file])

    class EmptyProvider(PerSpeakerProvider):
        def align(self, requests):
            self.seen_requests.extend(requests)
            return {}

    resolved, report = LipSyncResolver(EmptyProvider()).resolve(graph)

    assert report.dialogues_with_audio == 2
    assert report.dialogues_aligned == 0
    assert report.uses_real_alignment is False
    assert "*" in report.reasons


def test_resolver_skips_dialogues_without_audio_on_disk(tmp_path, speech_file):
    graph = build_graph([speech_file, str(tmp_path / "missing.mp3")])

    resolved, report = LipSyncResolver(PerSpeakerProvider()).resolve(graph)

    assert report.dialogues_total == 2
    assert report.dialogues_with_audio == 1
    assert report.dialogues_aligned == 1
    assert any("no audio file" in reason for reason in report.reasons.values())


def test_resolver_does_not_double_apply_the_dialogue_offset(speech_file):
    """Segment times stay audio-relative.

    The render worker adds the dialogue and scene offsets itself. If the resolver
    added them here too, the mouth would lead the voice by everything before it.
    """
    graph = build_graph([speech_file, speech_file])

    resolved, _ = LipSyncResolver(PerSpeakerProvider()).resolve(graph)
    dialogue = resolved.scenes[0].dialogues[0]

    assert dialogue.start_time == pytest.approx(0.4), "dialogue keeps its scene offset"
    assert dialogue.visemes[0].time == pytest.approx(0.02), (
        "viseme time must stay relative to the dialogue, not the scene"
    )


def test_resolver_is_a_no_op_without_a_provider(speech_file):
    graph = build_graph([speech_file, speech_file])
    resolved, report = LipSyncResolver(None).resolve(graph)

    assert report.engine == "none"
    assert report.dialogues_aligned == 0
    assert all(d.visemes == [] for scene in resolved.scenes for d in scene.dialogues)


def test_resolver_does_not_mutate_the_input_graph(speech_file):
    graph = build_graph([speech_file, speech_file])
    original_counts = [len(d.visemes) for s in graph.scenes for d in s.dialogues]

    LipSyncResolver(PerSpeakerProvider()).resolve(graph)

    assert [len(d.visemes) for s in graph.scenes for d in s.dialogues] == original_counts


def test_report_dict_is_json_serialisable(speech_file):
    _, report = LipSyncResolver(None).resolve(build_graph([speech_file, speech_file]))
    payload = report.to_dict()
    assert json.dumps(payload, ensure_ascii=False)
    assert payload["uses_real_alignment"] is False
