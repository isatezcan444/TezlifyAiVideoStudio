from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator
from tezlify_studio.domain.enums.studio_status import (
    AlignmentSource,
    CameraAngle,
    CameraMovement,
    CharacterPose,
    CharacterExpression,
    MouthViseme,
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

SUPPORTED_SCHEMA_VERSIONS = {"1.0"}
ALLOWED_FPS = {24, 25, 30, 60}

class CharacterStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hair_color: str = Field(default="#2C1810", pattern=r"^#[0-9a-fA-F]{6}$")
    skin_tone: str = Field(default="#F5D0A9", pattern=r"^#[0-9a-fA-F]{6}$")
    shirt_color: str = Field(default="#3B82F6", pattern=r"^#[0-9a-fA-F]{6}$")
    pants_color: str = Field(default="#1E293B", pattern=r"^#[0-9a-fA-F]{6}$")

class SceneCharacter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, description="Unique character ID (e.g. char_ali)")
    name: str = Field(..., min_length=1, description="Display name of the character")
    voice_id: str = Field(default="tr_yelda", min_length=1)
    style: CharacterStyle = Field(default_factory=CharacterStyle)

class CharacterPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_id: str = Field(..., min_length=1)
    position: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation_y: float = Field(default=0.0)
    pose: CharacterPose = Field(default=CharacterPose.STANDING)
    expression: CharacterExpression = Field(default=CharacterExpression.NEUTRAL)

    @model_validator(mode="after")
    def validate_position_3d(self) -> "CharacterPlacement":
        if len(self.position) != 3:
            raise InvalidSceneGraphException(
                f"Karakter pozisyonu tam 3 koordinat [x, y, z] içermelidir: {self.position}"
            )
        return self

class DialogueViseme(BaseModel):
    """One mouth shape over one interval of a dialogue.

    Stage 5.4 turned this from a schema placeholder into the render contract for
    lip sync. ``time`` and ``shape`` are kept for stored projects written before
    that; ``viseme`` / ``end_time`` / ``source`` are what the renderer now reads.
    The default ``source`` is ``ESTIMATED`` on purpose: anything that was written
    without saying otherwise was derived from text, not measured from audio.
    """

    model_config = ConfigDict(extra="forbid")

    time: float = Field(..., ge=0.0, description="Timestamp in seconds relative to dialogue start")
    shape: VisemeShape = Field(default=VisemeShape.X)
    end_time: Optional[float] = Field(default=None, ge=0.0)
    viseme: Optional[MouthViseme] = Field(default=None)
    phoneme: Optional[str] = Field(default=None, max_length=8)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source: AlignmentSource = Field(default=AlignmentSource.ESTIMATED)

    @model_validator(mode="after")
    def validate_viseme_span(self) -> "DialogueViseme":
        if self.end_time is not None and self.end_time <= self.time:
            raise InvalidDialogueTimingException(
                f"Viseme bitiş zamanı ({self.end_time}s) başlangıçtan ({self.time}s) büyük olmalıdır."
            )
        return self

    @property
    def duration_seconds(self) -> float:
        if self.end_time is None:
            return 0.0
        return round(self.end_time - self.time, 6)

    @property
    def is_measured(self) -> bool:
        """True only when this shape's timing came from the actual audio."""
        return self.source in (
            AlignmentSource.CTC_FORCED,
            AlignmentSource.ELEVENLABS_TIMING,
        )

class SceneDialogue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_id: str = Field(..., min_length=1)
    start_time: float = Field(..., ge=0.0, description="Start time in seconds within the scene")
    end_time: float = Field(..., gt=0.0, description="End time in seconds within the scene")
    text: str = Field(..., min_length=1, description="Spoken dialogue text")
    audio_file: Optional[str] = Field(default=None)
    visemes: List[DialogueViseme] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_timings(self) -> "SceneDialogue":
        if self.end_time <= self.start_time:
            raise InvalidDialogueTimingException(
                f"Diyalog bitiş zamanı ({self.end_time}s) başlangıç zamanından ({self.start_time}s) büyük olmalıdır."
            )
        return self

class SceneCamera(BaseModel):
    model_config = ConfigDict(extra="forbid")

    angle: CameraAngle = Field(default=CameraAngle.MEDIUM_SHOT)
    fov: float = Field(default=45.0, ge=10.0, le=120.0)
    movement: CameraMovement = Field(default=CameraMovement.STATIC)

class SceneBackground(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(default="preset", pattern="^(preset|color|custom)$")
    asset_id: str = Field(default="bg_modern_cafe", min_length=1)
    lighting: str = Field(default="warm_interior")

class SceneTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: TransitionType = Field(default=TransitionType.CUT)
    duration_seconds: float = Field(default=0.5, ge=0.0, le=5.0)

class StudioScene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(..., min_length=1, description="Unique scene identifier (e.g. scene_01)")
    sequence_order: int = Field(default=1, ge=1)
    duration_seconds: float = Field(..., gt=0.0, description="Total scene duration in seconds")
    background: SceneBackground = Field(default_factory=SceneBackground)
    camera: SceneCamera = Field(default_factory=SceneCamera)
    character_placements: List[CharacterPlacement] = Field(default_factory=list)
    dialogues: List[SceneDialogue] = Field(default_factory=list)
    transition: Optional[SceneTransition] = None

    @model_validator(mode="after")
    def validate_dialogues_within_scene(self) -> "StudioScene":
        for dlg in self.dialogues:
            if dlg.end_time > self.duration_seconds:
                raise InvalidDialogueTimingException(
                    f"Diyalog bitiş zamanı ({dlg.end_time}s), sahne süresini ({self.duration_seconds}s) aşamaz (Sahne: {self.scene_id})."
                )
        return self

class SceneResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)
    aspect_ratio: str = Field(default="16:9", pattern="^(16:9|9:16|1:1)$")
    fps: int = Field(default=30)

    @model_validator(mode="after")
    def validate_fps(self) -> "SceneResolution":
        if self.fps not in ALLOWED_FPS:
            raise InvalidResolutionException(
                f"Desteklenmeyen FPS: {self.fps}. İzin verilen değerler: {sorted(list(ALLOWED_FPS))}"
            )
        return self

class SceneGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0")
    project_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = Field(default="")
    resolution: SceneResolution = Field(default_factory=SceneResolution)
    characters: List[SceneCharacter] = Field(..., min_length=1)
    scenes: List[StudioScene] = Field(..., min_length=1)

    @property
    def total_duration_seconds(self) -> float:
        return sum(s.duration_seconds for s in self.scenes)

    @model_validator(mode="after")
    def validate_scene_graph_integrity(self) -> "SceneGraph":
        # 1. Schema version check
        if self.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise UnsupportedSchemaVersionException(
                self.schema_version,
                supported=", ".join(sorted(list(SUPPORTED_SCHEMA_VERSIONS)))
            )

        # 2. Title non-blank
        if not self.title.strip():
            raise InvalidSceneGraphException("Proje başlığı boş olamaz.")

        # 3. Unique character IDs
        seen_char_ids = set()
        for char in self.characters:
            if char.id in seen_char_ids:
                raise DuplicateCharacterIdException(char.id)
            seen_char_ids.add(char.id)

        # 4. Unique scene IDs
        seen_scene_ids = set()
        for scene in self.scenes:
            if scene.scene_id in seen_scene_ids:
                raise DuplicateSceneIdException(scene.scene_id)
            seen_scene_ids.add(scene.scene_id)

            # 5. Character references in placements
            for placement in scene.character_placements:
                if placement.character_id not in seen_char_ids:
                    raise CharacterNotFoundInSceneException(
                        placement.character_id,
                        f"Sahne '{scene.scene_id}' yerleşimi"
                    )

            # 6. Character references in dialogues
            for dlg in scene.dialogues:
                if dlg.character_id not in seen_char_ids:
                    raise CharacterNotFoundInSceneException(
                        dlg.character_id,
                        f"Sahne '{scene.scene_id}' diyaloğu"
                    )

        return self
