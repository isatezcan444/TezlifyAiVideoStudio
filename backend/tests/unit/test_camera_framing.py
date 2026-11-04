"""Stage 5.3 — format-aware camera framing.

These tests pin the geometry that makes a 9:16 export a real vertical shot rather
than a landscape frame with dead space: the profile registry, the closed-form
camera solve, and the projection that proves the cast lands inside the safe area.
"""

import pytest

from tezlify_studio.domain.value_objects.camera_framing import (
    LANDSCAPE,
    PORTRAIT,
    SQUARE,
    FramingProfile,
    FramingSolve,
    SubjectBounds,
    intent_for_angle,
    profile_for_aspect,
    profile_for_dimensions,
    screen_box,
    solve_camera,
    visible_extents_at_plane,
)

# Head-to-feet span of the built Ali rig, measured from the character builder.
STANDING_HEIGHT = 1.72


def two_cast_bounds(gap: float = 0.9) -> SubjectBounds:
    return SubjectBounds(x_min=-gap, x_max=gap, z_top=STANDING_HEIGHT, z_bottom=0.0)


def profile_for(aspect: str) -> FramingProfile:
    return profile_for_aspect(aspect)


# ----------------------------------------------------------------------
# Profiles
# ----------------------------------------------------------------------

def test_each_delivery_format_has_its_own_framing_profile():
    assert profile_for_aspect("16:9").key == "landscape"
    assert profile_for_aspect("9:16").key == "portrait"
    assert profile_for_aspect("1:1").key == "square"

    assert (LANDSCAPE.width, LANDSCAPE.height) == (1920, 1080)
    assert (PORTRAIT.width, PORTRAIT.height) == (1080, 1920)
    assert (SQUARE.width, SQUARE.height) == (1080, 1080)


def test_unknown_aspect_falls_back_to_landscape_instead_of_crashing():
    assert profile_for_aspect(None).key == "landscape"
    assert profile_for_aspect("4:3").key == "landscape"
    assert profile_for_aspect("garbage").key == "landscape"


def test_dimensions_alone_recover_the_profile_for_legacy_scene_graphs():
    assert profile_for_dimensions(1920, 1080).key == "landscape"
    assert profile_for_dimensions(1080, 1920).key == "portrait"
    assert profile_for_dimensions(1080, 1080).key == "square"


def test_portrait_reserves_more_bottom_area_than_landscape():
    """Platform UI and burned-in subtitles eat the bottom of a phone screen."""
    assert PORTRAIT.safe.bottom > SQUARE.safe.bottom > LANDSCAPE.safe.bottom
    for profile in (LANDSCAPE, PORTRAIT, SQUARE):
        assert 0.0 < profile.safe.height_ratio < 1.0
        assert 0.0 < profile.safe.width_ratio < 1.0
        assert profile.safe.top < profile.safe.center_y < 1.0 - profile.safe.bottom


def test_subject_fill_leaves_margin_inside_the_safe_area():
    for profile in (LANDSCAPE, PORTRAIT, SQUARE):
        assert 0.5 < profile.subject_fill <= 1.0
        assert 0.0 < profile.horizontal_spacing_ratio <= 1.0


# ----------------------------------------------------------------------
# Shot intents
# ----------------------------------------------------------------------

@pytest.mark.parametrize(
    "angle,key",
    [
        ("two_shot", "two_shot"),
        ("WIDE_SHOT", "wide"),
        ("establishing", "wide"),
        ("close_up", "close_up"),
        ("shoulder_shot", "shoulder"),
        ("medium_shot", "medium_shot"),
        ("", "medium_shot"),
        (None, "medium_shot"),
        ("unknown_angle", "medium_shot"),
    ],
)
def test_angle_names_map_to_a_shot_intent(angle, key):
    assert intent_for_angle(angle).key == key


def test_wider_shows_keep_more_body_and_shorter_shows_keep_less():
    assert intent_for_angle("wide").body_crop > intent_for_angle("two_shot").body_crop
    assert intent_for_angle("two_shot").body_crop > intent_for_angle("medium_shot").body_crop
    assert intent_for_angle("medium_shot").body_crop > intent_for_angle("close_up").body_crop
    assert intent_for_angle("wide").base_lens < intent_for_angle("close_up").base_lens


# ----------------------------------------------------------------------
# The solve
# ----------------------------------------------------------------------

def test_portrait_two_shot_fills_the_frame_instead_of_letterboxing():
    """The regression this stage exists for.

    A landscape camera reused for 9:16 leaves the cast in a thin band with dead
    wall above and below. The solved portrait camera must put the cast on the
    middle of the safe band and give the shot real presence.
    """
    landscape = solve_camera(LANDSCAPE, two_cast_bounds(), intent_for_angle("two_shot"))
    bounds, portrait = _framed(PORTRAIT, "two_shot", two_cast_bounds())

    assert portrait.distance < landscape.distance, "portrait must push in, not back up"
    assert portrait.fits and landscape.fits

    box = screen_box(PORTRAIT, portrait, bounds)
    assert box["x0"] >= 0.0, "cast must be on screen horizontally"
    assert box["x1"] <= 1.0
    assert box["y_top"] >= 0.0, "heads must not be cut"
    assert box["y_bottom"] <= 1.0, "bodies must not be cut"

    # Subject must occupy the safe band, not a slice of it.
    subject_share = box["y_bottom"] - box["y_top"]
    assert subject_share > 0.45, f"portrait subject fills only {subject_share:.2f} of the frame"


def test_landscape_two_shot_is_not_tighter_than_before_the_change():
    """16:9 delivery must keep its quality: the cast stays fully framed with headroom."""
    bounds, solve = _framed(LANDSCAPE, "two_shot", two_cast_bounds())
    box = screen_box(LANDSCAPE, solve, bounds)

    assert solve.fits
    assert box["y_top"] >= LANDSCAPE.safe.top - 0.02
    assert box["y_bottom"] <= 1.0 - LANDSCAPE.safe.bottom + 0.06
    assert box["x0"] > 0.0 and box["x1"] < 1.0


def test_single_speaker_is_centred_on_itself():
    bounds = SubjectBounds(x_min=-0.85, x_max=-0.25, z_top=STANDING_HEIGHT, z_bottom=0.0)
    solve = solve_camera(PORTRAIT, bounds.scale_x_about(bounds.center_x, PORTRAIT.horizontal_spacing_ratio),
                         intent_for_angle("medium_shot"))

    assert abs(solve.target_x - bounds.center_x) < 1e-6
    assert abs(solve.camera_x - bounds.center_x) < 1e-6

    box = screen_box(PORTRAIT, solve, bounds)
    centre = (box["x0"] + box["x1"]) / 2.0
    assert abs(centre - 0.5) < 0.02


def test_two_characters_side_by_side_both_stay_visible():
    """A naive centre crop of a landscape frame would cut one of them."""
    bounds, solve = _framed(PORTRAIT, "two_shot", two_cast_bounds(gap=1.1))
    box = screen_box(PORTRAIT, solve, bounds)

    assert solve.fits
    assert box["x0"] >= 0.0 and box["x1"] <= 1.0


def test_portrait_narrows_the_cast_spacing_so_the_camera_can_push_in():
    spread_16_9 = two_cast_bounds().scale_x_about(0.0, LANDSCAPE.horizontal_spacing_ratio)
    spread_9_16 = two_cast_bounds().scale_x_about(0.0, PORTRAIT.horizontal_spacing_ratio)

    assert LANDSCAPE.horizontal_spacing_ratio == 1.0
    assert spread_9_16.width < spread_16_9.width
    assert abs(spread_9_16.center_x) < 1e-9


def test_tall_frame_opens_the_crop_towards_the_feet():
    """Portrait height should be spent on the cast, not on wall."""
    bounds = two_cast_bounds()
    landscape_box, _ = _framed(LANDSCAPE, "two_shot", bounds)
    portrait_box, _ = _framed(PORTRAIT, "two_shot", bounds)

    assert LANDSCAPE.body_crop_adjust == 1.0
    assert PORTRAIT.body_crop_adjust > 1.0
    assert portrait_box.height > landscape_box.height
    assert portrait_box.z_bottom < landscape_box.z_bottom
    assert portrait_box.z_bottom >= 0.0, "crop may not invent body below the feet"


def test_close_up_frames_head_and_shoulders_only():
    bounds = SubjectBounds(-0.3, 0.3, STANDING_HEIGHT, 0.0)
    box, solve = _framed(PORTRAIT, "close_up", bounds)

    assert box.height < STANDING_HEIGHT * 0.5
    assert abs(box.z_top - STANDING_HEIGHT) < 1e-9
    assert solve.fits
    assert solve.distance <= PORTRAIT.max_distance


def test_lens_opens_up_when_the_rig_cannot_back_far_enough():
    """A wide cast spread is framed by widening the lens, not by clipping.

    At 38mm this spread would need 13m of distance; the rig stops at 9m, so the
    solve trades focal length for reach and still keeps every character on screen.
    """
    bounds = SubjectBounds(-5.0, 5.0, STANDING_HEIGHT, 0.0)
    intent = intent_for_angle("wide")
    solve = solve_camera(PORTRAIT, bounds, intent)

    assert solve.lens < intent.base_lens
    assert solve.lens >= PORTRAIT.min_lens
    assert solve.distance <= PORTRAIT.max_distance + 1e-9
    assert solve.fits, "widening must recover a framing that keeps the whole cast"


def test_beyond_the_rig_limits_the_solve_reports_that_it_could_not_fit():
    """Never silently clip: an impossible spread is flagged so the worker can warn."""
    bounds = SubjectBounds(-14.0, 14.0, STANDING_HEIGHT, 0.0)
    solve = solve_camera(PORTRAIT, bounds, intent_for_angle("wide"))

    assert solve.lens == PORTRAIT.min_lens
    assert solve.distance == PORTRAIT.max_distance
    assert solve.fits is False


def test_distance_is_clamped_to_the_physical_rig_limits():
    tiny = SubjectBounds(-0.02, 0.02, 0.10, 0.0)
    solve = solve_camera(PORTRAIT, tiny, intent_for_angle("close_up"))
    assert solve.distance >= PORTRAIT.min_distance


def test_visible_field_of_view_follows_the_sensor_fit_formula():
    """Cross-check the solve against the closed form the docstring promises."""
    for profile in (LANDSCAPE, PORTRAIT, SQUARE):
        bounds, solve = _framed(profile, "two_shot", two_cast_bounds())
        k = 18.0 / solve.lens
        assert solve.visible_width == pytest.approx(2.0 * solve.distance * k, rel=1e-9)
        assert solve.visible_height == pytest.approx(
            solve.visible_width * profile.height / profile.width, rel=1e-9
        )
        assert solve.safe_width == pytest.approx(
            solve.visible_width * profile.safe.width_ratio, rel=1e-9
        )


def test_wider_frame_ratio_shows_more_vertical_world_at_the_same_distance():
    """Same lens, same distance: 9:16 must see further up than 16:9.

    This is the geometry that turns an unmanaged portrait frame into black sky,
    and the reason the backdrop has to be solved alongside the camera.
    """
    bounds = two_cast_bounds()
    intent = intent_for_angle("two_shot")
    landscape = solve_camera(LANDSCAPE, bounds, intent)
    portrait = solve_camera(PORTRAIT, bounds, intent)

    ratio_l = landscape.visible_height / landscape.visible_width
    ratio_p = portrait.visible_height / portrait.visible_width
    assert ratio_p == pytest.approx(1920 / 1080, rel=1e-9)
    assert ratio_l == pytest.approx(1080 / 1920, rel=1e-9)
    assert ratio_p > ratio_l


def test_backdrop_coverage_grows_with_the_frame():
    """The set must cover what the camera can see, or headroom becomes black void."""
    for profile in (LANDSCAPE, PORTRAIT, SQUARE):
        _, solve = _framed(profile, "two_shot", two_cast_bounds())
        x0, x1, z0, z1 = visible_extents_at_plane(profile, solve, plane_y=5.0)

        assert x1 > x0 and z1 > z0
        assert z1 > 1.72, f"{profile.key}: wall must reach above the cast's heads"
        assert z0 <= 0.0, f"{profile.key}: floor line must be covered"
        # Portrait sees the most set, which is exactly where the old hardcoded
        # 2.4x wall extension was guessed rather than measured.
        if profile.key == "portrait":
            assert z1 > 3.0


def test_safe_area_centre_pulls_the_aim_up_in_portrait():
    bounds = two_cast_bounds()
    solve = solve_camera(PORTRAIT, bounds.scale_x_about(0.0, PORTRAIT.horizontal_spacing_ratio),
                         intent_for_angle("two_shot"))
    expected = bounds.center_z + (PORTRAIT.safe.center_y - 0.5) * solve.visible_height
    assert solve.target_z == pytest.approx(expected, rel=1e-9)
    assert PORTRAIT.safe.center_y < 0.5, "portrait should sit the cast above the middle row"


def test_camera_sits_above_the_aim_by_the_shots_height_offset():
    intent = intent_for_angle("wide")
    solve = solve_camera(LANDSCAPE, two_cast_bounds(), intent)
    assert solve.camera_z == pytest.approx(solve.target_z + intent.height_offset, rel=1e-9)


def test_camera_is_placed_at_the_solved_distance_in_front_of_the_subject():
    solve = solve_camera(PORTRAIT, two_cast_bounds(), intent_for_angle("two_shot"))
    assert solve.camera_y == pytest.approx(-solve.distance, rel=1e-9)


def test_screen_projection_maps_world_height_to_frame_rows_monotonically():
    profile = PORTRAIT
    bounds = two_cast_bounds()
    solve = solve_camera(profile, bounds, intent_for_angle("two_shot"))

    head = screen_box(profile, solve, SubjectBounds(-0.3, 0.3, 1.72, 1.5))
    feet = screen_box(profile, solve, SubjectBounds(-0.3, 0.3, 0.3, 0.0))
    assert head["y_top"] < feet["y_top"], "higher in world space must be higher in frame"


def test_solve_is_deterministic_for_the_same_inputs():
    bounds = two_cast_bounds()
    intent = intent_for_angle("two_shot")
    first = solve_camera(PORTRAIT, bounds, intent)
    second = solve_camera(PORTRAIT, bounds, intent)
    assert first.to_dict() == second.to_dict()


def test_solve_report_carries_the_numbers_the_evidence_needs():
    solve = solve_camera(PORTRAIT, two_cast_bounds(), intent_for_angle("two_shot"))
    payload = solve.to_dict()
    for key in (
        "profile", "shot", "lens_mm", "distance_m", "camera", "target",
        "visible_width_m", "visible_height_m", "fill_width", "fill_height",
        "fits_safe_area", "limited_by",
    ):
        assert key in payload
    assert payload["profile"] == "portrait"
    assert len(payload["camera"]) == 3


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _framed(
    profile: FramingProfile, angle: str, bounds: SubjectBounds
) -> tuple[SubjectBounds, "FramingSolve"]:
    """Mirror exactly what the render worker does: narrow the cast, crop the shot, solve.

    The crop and the spacing are both format decisions, so a test that projects
    the unscaled box would be measuring a silhouette the camera was never asked to
    frame.
    """
    intent = intent_for_angle(angle)
    spaced = bounds.scale_x_about(bounds.center_x, profile.horizontal_spacing_ratio)
    crop = max(0.05, min(1.0, intent.body_crop * profile.body_crop_adjust))
    z_bottom = spaced.z_top - crop * (spaced.z_top - spaced.z_bottom)
    framed = SubjectBounds(spaced.x_min, spaced.x_max, spaced.z_top, z_bottom)
    return framed, solve_camera(profile, framed, intent)
