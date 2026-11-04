import pytest
from pydantic import ValidationError
from tezlify_studio.domain.value_objects.scene_graph import (
    SceneGraph,
    SceneResolution,
    SceneCharacter,
    CharacterStyle,
    StudioScene,
    SceneBackground,
    SceneCamera,
    CharacterPlacement,
    SceneDialogue,
    DialogueViseme,
    SceneTransition,
)
from tezlify_studio.domain.enums.studio_status import (
    CameraAngle,
    CameraMovement,
    CharacterPose,
    CharacterExpression,
    TransitionType,
    VisemeShape,
)
from tezlify_studio.domain.exceptions.studio_exceptions import (
    InvalidSceneGraphException,
    DuplicateSceneIdException,
    DuplicateCharacterIdException,
    CharacterNotFoundInSceneException,
    InvalidDialogueTimingException,
    InvalidResolutionException,
    UnsupportedSchemaVersionException,
)

def build_valid_scene_graph() -> SceneGraph:
    char1 = SceneCharacter(
        id="char_ali",
        name="Ali",
        voice_id="tr_yelda",
        style=CharacterStyle(hair_color="#2C1810", skin_tone="#F5D0A9", shirt_color="#3B82F6", pants_color="#1E293B"),
    )
    char2 = SceneCharacter(
        id="char_ayse",
        name="Ayşe",
        voice_id="tr_yelda",
        style=CharacterStyle(hair_color="#B45309", skin_tone="#FCE7D0", shirt_color="#EC4899", pants_color="#334155"),
    )
    scene1 = StudioScene(
        scene_id="scene_01",
        sequence_order=1,
        duration_seconds=15.0,
        background=SceneBackground(type="preset", asset_id="bg_modern_cafe", lighting="warm_interior"),
        camera=SceneCamera(angle=CameraAngle.MEDIUM_SHOT, fov=45.0, movement=CameraMovement.STATIC),
        character_placements=[
            CharacterPlacement(character_id="char_ali", position=[-1.0, 0.0, 0.0], pose=CharacterPose.STANDING),
            CharacterPlacement(character_id="char_ayse", position=[1.0, 0.0, 0.0], pose=CharacterPose.SITTING_TABLE),
        ],
        dialogues=[
            SceneDialogue(
                character_id="char_ali",
                start_time=1.0,
                end_time=5.0,
                text="Merhaba Ayşe!",
                visemes=[DialogueViseme(time=1.0, shape=VisemeShape.X), DialogueViseme(time=1.2, shape=VisemeShape.A)],
            ),
            SceneDialogue(
                character_id="char_ayse",
                start_time=6.0,
                end_time=10.0,
                text="Selam Ali, kahven hazır mı?",
                visemes=[DialogueViseme(time=6.0, shape=VisemeShape.X)],
            ),
        ],
        transition=SceneTransition(type=TransitionType.CROSSFADE, duration_seconds=0.5),
    )
    return SceneGraph(
        schema_version="1.0",
        project_id="proj_test_01",
        title="Kafede Karşılaşma",
        description="Test senaryosu",
        resolution=SceneResolution(width=1920, height=1080, aspect_ratio="16:9", fps=30),
        characters=[char1, char2],
        scenes=[scene1],
    )

def test_valid_scene_graph():
    sg = build_valid_scene_graph()
    assert sg.schema_version == "1.0"
    assert sg.title == "Kafede Karşılaşma"
    assert len(sg.characters) == 2
    assert len(sg.scenes) == 1
    assert sg.total_duration_seconds == 15.0

def test_json_serialization_roundtrip():
    sg = build_valid_scene_graph()
    json_str = sg.model_dump_json()
    assert "char_ali" in json_str
    assert "scene_01" in json_str

    deserialized = SceneGraph.model_validate_json(json_str)
    assert deserialized.project_id == sg.project_id
    assert deserialized.characters[0].name == "Ali"
    assert deserialized.scenes[0].duration_seconds == 15.0

def test_duplicate_character_id_raises():
    char1 = SceneCharacter(id="char_same", name="Ali")
    char2 = SceneCharacter(id="char_same", name="Ayşe")
    scene1 = StudioScene(scene_id="scene_01", sequence_order=1, duration_seconds=10.0)

    with pytest.raises(DuplicateCharacterIdException) as exc_info:
        SceneGraph(
            project_id="p1",
            title="Duplicate Char Test",
            characters=[char1, char2],
            scenes=[scene1],
        )
    assert "char_same" in str(exc_info.value)

def test_duplicate_scene_id_raises():
    char1 = SceneCharacter(id="char_1", name="Ali")
    scene1 = StudioScene(scene_id="scene_same", sequence_order=1, duration_seconds=10.0)
    scene2 = StudioScene(scene_id="scene_same", sequence_order=2, duration_seconds=10.0)

    with pytest.raises(DuplicateSceneIdException) as exc_info:
        SceneGraph(
            project_id="p1",
            title="Duplicate Scene Test",
            characters=[char1],
            scenes=[scene1, scene2],
        )
    assert "scene_same" in str(exc_info.value)

def test_character_placement_not_found_raises():
    char1 = SceneCharacter(id="char_1", name="Ali")
    scene1 = StudioScene(
        scene_id="scene_01",
        sequence_order=1,
        duration_seconds=10.0,
        character_placements=[CharacterPlacement(character_id="char_ghost", position=[0.0, 0.0, 0.0])],
    )
    with pytest.raises(CharacterNotFoundInSceneException) as exc_info:
        SceneGraph(
            project_id="p1",
            title="Ghost Char Test",
            characters=[char1],
            scenes=[scene1],
        )
    assert "char_ghost" in str(exc_info.value)

def test_dialogue_character_not_found_raises():
    char1 = SceneCharacter(id="char_1", name="Ali")
    scene1 = StudioScene(
        scene_id="scene_01",
        sequence_order=1,
        duration_seconds=10.0,
        dialogues=[SceneDialogue(character_id="char_unknown", start_time=1.0, end_time=4.0, text="Merhaba!")],
    )
    with pytest.raises(CharacterNotFoundInSceneException) as exc_info:
        SceneGraph(
            project_id="p1",
            title="Unknown Dlg Char Test",
            characters=[char1],
            scenes=[scene1],
        )
    assert "char_unknown" in str(exc_info.value)

def test_invalid_dialogue_timing_end_before_start():
    with pytest.raises(InvalidDialogueTimingException):
        SceneDialogue(character_id="char_1", start_time=5.0, end_time=3.0, text="Hatalı zaman!")

def test_dialogue_exceeding_scene_duration_raises():
    with pytest.raises(InvalidDialogueTimingException) as exc_info:
        StudioScene(
            scene_id="scene_01",
            sequence_order=1,
            duration_seconds=10.0,
            dialogues=[SceneDialogue(character_id="char_1", start_time=2.0, end_time=12.0, text="Çok uzun!")],
        )
    assert "sahne süresini" in str(exc_info.value)

def test_invalid_fps_raises():
    with pytest.raises(InvalidResolutionException) as exc_info:
        SceneResolution(fps=45)
    assert "45" in str(exc_info.value)

def test_empty_title_raises():
    char1 = SceneCharacter(id="char_1", name="Ali")
    scene1 = StudioScene(scene_id="scene_01", sequence_order=1, duration_seconds=10.0)
    with pytest.raises(InvalidSceneGraphException):
        SceneGraph(
            project_id="p1",
            title="   ",
            characters=[char1],
            scenes=[scene1],
        )

def test_unsupported_schema_version_raises():
    sg = build_valid_scene_graph()
    data = sg.model_dump()
    data["schema_version"] = "99.0"
    with pytest.raises(UnsupportedSchemaVersionException):
        SceneGraph.model_validate(data)
