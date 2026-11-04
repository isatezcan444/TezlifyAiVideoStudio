import pytest

from tezlify_studio.domain.exceptions.studio_exceptions import (
    InvalidCompositionException,
)
from tezlify_studio.domain.value_objects.video_composition import (
    AudioMixSettings,
    CompositionScene,
    CompositionTransition,
    SubtitleSettings,
    TextAnchor,
    TextLayer,
    VideoComposition,
    VideoFormat,
    build_composition_timeline,
    validate_composition_against_scene_ids,
)


def _composition(scenes, **kwargs):
    return VideoComposition(
        id="comp_test",
        project_id="proj_test",
        format=kwargs.pop("format", VideoFormat.LANDSCAPE_16_9),
        fps=kwargs.pop("fps", 30),
        scenes=scenes,
        **kwargs,
    )


def test_format_dimensions_are_authoritative():
    comp = _composition(
        [CompositionScene(scene_id="s1")],
        format=VideoFormat.PORTRAIT_9_16,
    )
    assert (comp.width, comp.height) == (1080, 1920)

    square = _composition(
        [CompositionScene(scene_id="s1")],
        format=VideoFormat.SQUARE_1_1,
    )
    assert (square.width, square.height) == (1080, 1080)

    landscape = _composition([CompositionScene(scene_id="s1")])
    assert (landscape.width, landscape.height) == (1920, 1080)


def test_crossfade_timeline_reduces_total_duration():
    comp = _composition(
        [
            CompositionScene(
                scene_id="s1",
                transition=CompositionTransition.CROSSFADE,
                transition_duration_seconds=0.5,
            ),
            CompositionScene(
                scene_id="s2",
                transition=CompositionTransition.CROSSFADE,
                transition_duration_seconds=0.5,
            ),
            CompositionScene(scene_id="s3"),
        ]
    )
    timeline = build_composition_timeline(comp, {"s1": 4.0, "s2": 3.0, "s3": 2.0})

    assert timeline.total_duration_seconds == pytest.approx(8.0)
    assert timeline.total_overlap_seconds == pytest.approx(1.0)
    assert timeline.entry_for("s1").start_time == pytest.approx(0.0)
    assert timeline.entry_for("s2").start_time == pytest.approx(3.5)
    assert timeline.entry_for("s3").start_time == pytest.approx(6.0)
    assert timeline.entry_for("s3").end_time == pytest.approx(8.0)


def test_cut_and_fade_transitions_do_not_shorten_timeline():
    comp = _composition(
        [
            CompositionScene(scene_id="s1", transition=CompositionTransition.FADE_OUT, transition_duration_seconds=0.4),
            CompositionScene(scene_id="s2", transition=CompositionTransition.FADE_IN, transition_duration_seconds=0.4),
            CompositionScene(scene_id="s3"),
        ]
    )
    timeline = build_composition_timeline(comp, {"s1": 2.0, "s2": 2.0, "s3": 1.0})
    assert timeline.total_duration_seconds == pytest.approx(5.0)
    assert timeline.entry_for("s2").start_time == pytest.approx(2.0)
    assert timeline.entry_for("s3").start_time == pytest.approx(4.0)


def test_last_scene_fade_out_is_kept():
    comp = _composition(
        [
            CompositionScene(scene_id="s1"),
            CompositionScene(
                scene_id="s2",
                transition=CompositionTransition.FADE_OUT,
                transition_duration_seconds=0.5,
            ),
        ]
    )
    timeline = build_composition_timeline(comp, {"s1": 1.0, "s2": 2.0})
    assert timeline.entry_for("s2").transition == CompositionTransition.FADE_OUT


def test_crossfade_longer_than_scene_is_rejected():
    comp = _composition(
        [
            CompositionScene(
                scene_id="s1",
                transition=CompositionTransition.CROSSFADE,
                transition_duration_seconds=1.5,
            ),
            CompositionScene(scene_id="s2"),
        ]
    )
    with pytest.raises(InvalidCompositionException):
        build_composition_timeline(comp, {"s1": 1.0, "s2": 2.0})


def test_duplicate_scene_ids_are_rejected():
    with pytest.raises(InvalidCompositionException):
        _composition([CompositionScene(scene_id="s1"), CompositionScene(scene_id="s1")])


def test_scene_order_must_match_scene_graph_exactly():
    comp = _composition([CompositionScene(scene_id="s2"), CompositionScene(scene_id="s1")])
    # Reordering is allowed, but missing/extra scenes are not.
    validate_composition_against_scene_ids(comp, ["s1", "s2"])

    with pytest.raises(InvalidCompositionException):
        validate_composition_against_scene_ids(comp, ["s1", "s2", "s3"])


def test_text_layer_validation_and_fade_timing():
    layer = TextLayer(
        id="title",
        text="ŞİĞÜÖÇ ıİ",
        start_time=0.5,
        end_time=2.5,
        anchor=TextAnchor.TOP_CENTER,
        font_size=72,
        fade_in_seconds=0.3,
        fade_out_seconds=0.3,
    )
    comp = _composition([CompositionScene(scene_id="s1")], text_layers=[layer])
    assert comp.text_layers[0].text == "ŞİĞÜÖÇ ıİ"

    with pytest.raises(InvalidCompositionException):
        TextLayer(id="bad", text="x", start_time=2.0, end_time=2.0)

    with pytest.raises(InvalidCompositionException):
        TextLayer(
            id="bad-fade",
            text="x",
            start_time=0.0,
            end_time=1.0,
            fade_in_seconds=0.8,
            fade_out_seconds=0.8,
        )


def test_subtitle_and_audio_defaults_are_safe():
    comp = _composition([CompositionScene(scene_id="s1")])
    assert comp.subtitles.enabled is True
    assert comp.subtitles.burn_in is True
    assert comp.audio.music_file is None
    assert comp.audio.limiter_enabled is True


def test_unsupported_fps_is_rejected():
    with pytest.raises(InvalidCompositionException):
        _composition([CompositionScene(scene_id="s1")], fps=29)
