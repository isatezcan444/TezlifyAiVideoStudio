"""Helpers for creating default Stage 4.5 compositions from a SceneGraph."""

from __future__ import annotations

from typing import Dict, List

from tezlify_studio.domain.value_objects.scene_graph import SceneGraph
from tezlify_studio.domain.value_objects.video_composition import (
    CompositionScene,
    CompositionTimeline,
    CompositionTransition,
    TextAnchor,
    TextLayer,
    VideoComposition,
    VideoFormat,
    build_composition_timeline,
)


def scene_durations_for(scene_graph: SceneGraph) -> Dict[str, float]:
    return {scene.scene_id: float(scene.duration_seconds) for scene in scene_graph.scenes}


def default_composition_for(
    project_id: str,
    scene_graph: SceneGraph,
    video_format: VideoFormat = VideoFormat.LANDSCAPE_16_9,
) -> VideoComposition:
    ordered = sorted(scene_graph.scenes, key=lambda s: (s.sequence_order, s.scene_id))
    total = sum(float(s.duration_seconds) for s in ordered)

    text_layers: List[TextLayer] = []
    if total >= 2.0:
        opening_end = min(3.0, max(1.2, total * 0.28))
        text_layers.append(
            TextLayer(
                id="opening_title",
                text=scene_graph.title,
                start_time=0.25,
                end_time=round(opening_end, 3),
                anchor=TextAnchor.CENTER,
                x_ratio=0.5,
                y_ratio=0.5,
                font_size=72,
                background_opacity=0.0,
                background_color="#000000",
                fade_in_seconds=0.35,
                fade_out_seconds=0.35,
            )
        )

    if total >= 6.0:
        closing_start = max(0.0, total - 2.8)
        text_layers.append(
            TextLayer(
                id="closing_title",
                text="Tezlify AI Video Studio",
                start_time=round(closing_start, 3),
                end_time=round(total - 0.15, 3),
                anchor=TextAnchor.BOTTOM_CENTER,
                x_ratio=0.5,
                y_ratio=0.9,
                font_size=40,
                background_opacity=0.45,
                fade_in_seconds=0.3,
                fade_out_seconds=0.3,
            )
        )

    return VideoComposition(
        id=f"comp_{project_id}",
        project_id=project_id,
        name="Ana Kompozisyon",
        format=video_format,
        fps=scene_graph.resolution.fps,
        scenes=[
            CompositionScene(
                scene_id=scene.scene_id,
                transition=CompositionTransition.CUT,
                transition_duration_seconds=0.0,
            )
            for scene in ordered
        ],
        text_layers=text_layers,
    )


def timeline_for(composition: VideoComposition, scene_graph: SceneGraph) -> CompositionTimeline:
    return build_composition_timeline(composition, scene_durations_for(scene_graph))
