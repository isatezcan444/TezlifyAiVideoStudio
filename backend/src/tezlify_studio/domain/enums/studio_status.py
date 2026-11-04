from enum import Enum

class StudioProjectStatus(str, Enum):
    DRAFT = "draft"
    SCENARIO_READY = "scenario_ready"
    RENDER_QUEUED = "render_queued"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"

class RenderJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

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
    SITTING = "sitting"
    SITTING_TABLE = "sitting_table"
    GESTURING = "gesturing"
    WALKING = "walking"
    POINTING = "pointing"
    IDLE = "idle"

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

class MouthViseme(str, Enum):
    """Lip-rounded mouth shapes used by Stage 5.4 viseme-driven lip sync.

    ``VisemeShape`` above is the legacy letter set that nothing ever read. These
    names carry the articulation the renderer actually needs, and they group
    Turkish sounds by how the lips look rather than by phonemic identity, which is
    what makes them usable on a 2.5D mouth mesh.
    """

    REST = "REST"                    # silence: lips closed and relaxed
    CLOSED = "CLOSED"                # p, b, m
    FV = "FV"                        # f, v
    DENTAL = "DENTAL"                # t, d, n, l
    SIBILANT = "SIBILANT"            # s, z, ş, j, ç
    VELAR = "VELAR"                  # k, g, ğ
    OPEN = "OPEN"                    # a, e
    WIDE = "WIDE"                    # i, ı
    ROUND = "ROUND"                  # o, ö
    NARROW_ROUND = "NARROW_ROUND"    # u, ü

class AlignmentSource(str, Enum):
    """Where a lip-sync timing came from, and therefore whether it is real.

    ``ESTIMATED`` and ``LEGACY_FLAP`` are explicitly not real alignment: they are
    derived from text length or a fixed frame cycle. Keeping them in the same field
    is what stops a report or a UI from claiming phoneme accuracy it does not have.
    """

    CTC_FORCED = "ctc_forced"              # local forced alignment on the real audio
    ELEVENLABS_TIMING = "elevenlabs_timing"  # provider timestamps for the real audio
    ESTIMATED = "estimated"                # text-length heuristic, NOT alignment
    LEGACY_FLAP = "legacy_flap"            # pre-5.4 open/close cycle, NOT alignment
    NONE = "none"                          # no mouth animation for this dialogue

class AssetCategory(str, Enum):
    BACKGROUND = "background"
    PROP = "prop"
    LIGHTING = "lighting"

class AssetFormat(str, Enum):
    BLEND = "blend"
    PNG = "png"
    OBJ = "obj"
    GLTF = "gltf"

class HairStyle(str, Enum):
    SHORT_PARTED = "short_parted"
    BOB_CUT = "bob_cut"
    LONG_STRAIGHT = "long_straight"
    CURLY = "curly"
    PONYTAIL = "ponytail"

class EyeStyle(str, Enum):
    DOT = "dot"
    ROUND = "round"
    ANIME = "anime"
    MINIMAL = "minimal"

class ClothingStyle(str, Enum):
    CASUAL = "casual"
    FORMAL = "formal"
    HOODIE = "hoodie"
    SPORTY = "sporty"

