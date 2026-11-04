from enum import Enum

class StudioProjectStatus(str, Enum):
    DRAFT = "draft"
    SCENARIO_READY = "scenario_ready"
    RENDER_QUEUED = "render_queued"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"

class CameraAngle(str, Enum):
    WIDE_SHOT = "wide_shot"
    MEDIUM_SHOT = "medium_shot"
    CLOSE_UP = "close_up"
    TWO_SHOT = "two_shot"
    OVER_SHOULDER = "over_shoulder"

class CameraMovement(str, Enum):
    STATIC = "static"
    SLOW_PAN_RIGHT = "slow_pan_right"
    SLOW_PAN_LEFT = "slow_pan_left"
    SLOW_ZOOM_IN = "slow_zoom_in"
    SLOW_ZOOM_OUT = "slow_zoom_out"

class CharacterPose(str, Enum):
    STANDING = "standing"
    SITTING_TABLE = "sitting_table"
    GESTURING = "gesturing"
    WALKING = "walking"
    POINTING = "pointing"

class CharacterExpression(str, Enum):
    NEUTRAL = "neutral"
    CHEERFUL = "cheerful"
    SURPRISED = "surprised"
    ANGRY = "angry"
    SAD = "sad"
    THINKING = "thinking"

class TransitionType(str, Enum):
    CUT = "cut"
    CROSSFADE = "crossfade"
    FADE_TO_BLACK = "fade_to_black"

class VisemeShape(str, Enum):
    X = "X"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    H = "H"
    O = "O"
    U = "U"
