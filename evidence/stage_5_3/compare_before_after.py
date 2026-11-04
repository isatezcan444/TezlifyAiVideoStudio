#!/usr/bin/env python3
"""Stage 5.3 before/after framing comparison.

Projects the camera that Stage 5.2.1 shipped — the fixed per-angle rig in
``get_camera_positions`` — through the same projection the new solve uses, so the
"before" and "after" numbers are measured with one ruler rather than one being
guessed from pixels.

Usage:
    PYTHONPATH=backend/src .venv/bin/python evidence/stage_5_3/compare_before_after.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "backend", "src"))
sys.path.insert(0, HERE)

from measure import write_json  # noqa: E402
from tezlify_studio.domain.value_objects.camera_framing import (  # noqa: E402
    PORTRAIT,
    SQUARE,
    FramingSolve,
    LANDSCAPE,
    SubjectBounds,
    intent_for_angle,
    profile_for_aspect,
    screen_box,
    solve_camera,
)

# The rig Stage 5.2.1 used for a two_shot, read from get_camera_positions in
# commit b25aaea: base ((0, -3.2, 1.25), (0, 0, 1.05), 45.0) with the 9:16 branch
# multiplying distance by 1.04, adding 0.02 to both heights and 5% to the lens.
LEGACY_RIG = {
    "16:9": {"distance": 3.20, "lens": 45.00, "target_z": 1.05, "camera_z": 1.25},
    "9:16": {"distance": 3.328, "lens": 47.25, "target_z": 1.07, "camera_z": 1.27},
    "1:1": {"distance": 3.232, "lens": 47.25, "target_z": 1.05, "camera_z": 1.30},
}

# Ali + Ayşe standing side by side at the authored x = -0.55 / +0.55, measured from
# the character builder geometry (hair top 1.72 m) and cropped as a two-shot.
SUBJECT_SPAN = 1.72
AUTHORED_HALF_SPREAD = 0.55
ARM_HALF_REACH = 0.33
TWO_SHOT_CROP = 0.82


def legacy_solve(aspect: str) -> FramingSolve:
    """Rebuild the old camera as a FramingSolve so the projection is shared."""
    profile = profile_for_aspect(aspect)
    rig = LEGACY_RIG[aspect]
    k = 18.0 / rig["lens"]
    visible_width = 2.0 * rig["distance"] * k
    visible_height = visible_width * (profile.height / profile.width)
    return FramingSolve(
        lens=rig["lens"],
        distance=rig["distance"],
        camera_x=0.0,
        camera_y=-rig["distance"],
        camera_z=rig["camera_z"],
        target_x=0.0,
        target_z=rig["target_z"],
        visible_width=visible_width,
        visible_height=visible_height,
        safe_width=visible_width * profile.safe.width_ratio,
        safe_height=visible_height * profile.safe.height_ratio,
        fits=False,
        limited_by="legacy",
        subject=SubjectBounds(
            x_min=-(AUTHORED_HALF_SPREAD + ARM_HALF_REACH),
            x_max=AUTHORED_HALF_SPREAD + ARM_HALF_REACH,
            z_top=SUBJECT_SPAN,
            z_bottom=SUBJECT_SPAN * (1.0 - TWO_SHOT_CROP),
        ),
        profile_key=profile.key,
        shot_key="two_shot",
    )


def new_solve(aspect: str) -> FramingSolve:
    profile = profile_for_aspect(aspect)
    intent = intent_for_angle("two_shot")
    crop = min(1.0, TWO_SHOT_CROP * profile.body_crop_adjust)
    bounds = SubjectBounds(
        x_min=-(AUTHORED_HALF_SPREAD + ARM_HALF_REACH),
        x_max=AUTHORED_HALF_SPREAD + ARM_HALF_REACH,
        z_top=SUBJECT_SPAN,
        z_bottom=SUBJECT_SPAN * (1.0 - crop),
    ).scale_x_about(0.0, profile.horizontal_spacing_ratio)
    return solve_camera(profile, bounds, intent)


def main() -> None:
    rows = []
    for aspect in ("16:9", "9:16", "1:1"):
        profile = profile_for_aspect(aspect)
        for variant, solve in (("legacy", legacy_solve(aspect)), ("stage_5_3", new_solve(aspect))):
            box = screen_box(profile, solve, solve.subject)
            frame_share = box["y_bottom"] - box["y_top"]
            safe_share = frame_share / profile.safe.height_ratio
            rows.append({
                "aspect_ratio": aspect,
                "variant": variant,
                "lens_mm": round(solve.lens, 2),
                "distance_m": round(solve.distance, 3),
                "visible_width_m": round(solve.visible_width, 3),
                "visible_height_m": round(solve.visible_height, 3),
                "subject_x0": box["x0"],
                "subject_x1": box["x1"],
                "subject_y_top": box["y_top"],
                "subject_y_bottom": box["y_bottom"],
                "subject_share_of_frame_height": round(frame_share, 4),
                "subject_share_of_safe_band": round(safe_share, 4),
                "headroom_above_head": round(box["y_top"], 4),
                "dead_space_below_body": round(1.0 - box["y_bottom"], 4),
                "inside_safe_area": (
                    box["x0"] >= profile.safe.left
                    and box["x1"] <= 1.0 - profile.safe.right
                    and box["y_top"] >= profile.safe.top
                    and box["y_bottom"] <= 1.0 - profile.safe.bottom
                ),
            })

        print(f"\n== {aspect} ==")
        for row in [r for r in rows if r["aspect_ratio"] == aspect]:
            print(
                f"  {row['variant']:>10}: lens {row['lens_mm']:.2f}mm "
                f"d {row['distance_m']:.2f}m  subject occupies "
                f"{row['subject_share_of_frame_height']:.3f} of frame height "
                f"({row['subject_share_of_safe_band']:.3f} of the safe band), "
                f"dead space below body {row['dead_space_below_body']:.3f}, "
                f"inside safe area {row['inside_safe_area']}"
            )

    write_json(os.path.join(HERE, "before_after_framing.json"), rows)
    print(f"\nWrote {os.path.join(HERE, 'before_after_framing.json')}")


if __name__ == "__main__":
    main()
