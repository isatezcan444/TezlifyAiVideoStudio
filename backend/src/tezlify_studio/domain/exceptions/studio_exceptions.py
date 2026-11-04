from typing import Optional


class StudioDomainException(Exception):
    """Base exception for all Studio domain errors."""
    def __init__(self, message: str, error_code: str = "STUDIO_ERROR"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code

class InvalidSceneGraphException(StudioDomainException):
    def __init__(self, message: str, error_code: str = "INVALID_SCENE_GRAPH"):
        super().__init__(message, error_code)

class DuplicateSceneIdException(InvalidSceneGraphException):
    def __init__(self, scene_id: str):
        super().__init__(
            f"Scene ID '{scene_id}' zaten mevcut. Sahne ID'leri benzersiz olmalıdır.",
            error_code="DUPLICATE_SCENE_ID"
        )
        self.scene_id = scene_id

class DuplicateCharacterIdException(InvalidSceneGraphException):
    def __init__(self, character_id: str):
        super().__init__(
            f"Karakter ID '{character_id}' zaten tanımlı. Karakter ID'leri benzersiz olmalıdır.",
            error_code="DUPLICATE_CHARACTER_ID"
        )
        self.character_id = character_id

class CharacterNotFoundInSceneException(InvalidSceneGraphException):
    def __init__(self, character_id: str, context: str = ""):
        ctx_msg = f" ({context})" if context else ""
        super().__init__(
            f"Karakter ID '{character_id}' proje karakter listesinde bulunamadı{ctx_msg}.",
            error_code="CHARACTER_NOT_FOUND"
        )
        self.character_id = character_id

class InvalidDialogueTimingException(InvalidSceneGraphException):
    def __init__(self, message: str):
        super().__init__(message, error_code="INVALID_DIALOGUE_TIMING")

class InvalidResolutionException(InvalidSceneGraphException):
    def __init__(self, message: str):
        super().__init__(message, error_code="INVALID_RESOLUTION")

class UnsupportedSchemaVersionException(StudioDomainException):
    def __init__(self, version: str, supported: str = "1.0"):
        super().__init__(
            f"Desteklenmeyen Scene Graph şema sürümü: '{version}'. Desteklenen: {supported}",
            error_code="UNSUPPORTED_SCHEMA_VERSION"
        )
        self.version = version

class StudioProjectNotFoundException(StudioDomainException):
    def __init__(self, project_id: str):
        super().__init__(
            f"Studio projesi bulunamadı: '{project_id}'",
            error_code="PROJECT_NOT_FOUND"
        )
        self.project_id = project_id

class StoryGenerationException(StudioDomainException):
    def __init__(self, message: str):
        super().__init__(message, error_code="STORY_GENERATION_FAILED")

class CharacterNotFoundException(StudioDomainException):
    def __init__(self, character_id: str):
        super().__init__(
            f"Karakter bulunamadı: '{character_id}'",
            error_code="CHARACTER_NOT_FOUND"
        )
        self.character_id = character_id

class InvalidColorHexException(StudioDomainException):
    def __init__(self, color_field: str, value: str):
        super().__init__(
            f"Geçersiz HEX renk kodu '{value}' ({color_field} alanı için). Örnek format: #3B82F6",
            error_code="INVALID_HEX_COLOR"
        )
        self.color_field = color_field
        self.value = value

class AssetNotFoundException(StudioDomainException):
    def __init__(self, asset_id: str):
        super().__init__(
            f"Varlık (Asset) bulunamadı: '{asset_id}'",
            error_code="ASSET_NOT_FOUND"
        )
        self.asset_id = asset_id

class DuplicateAssetIdException(StudioDomainException):
    def __init__(self, asset_id: str):
        super().__init__(
            f"Varlık ID '{asset_id}' zaten mevcut. Asset ID'leri benzersiz olmalıdır.",
            error_code="DUPLICATE_ASSET_ID"
        )
        self.asset_id = asset_id

class BlenderRenderException(StudioDomainException):
    def __init__(self, message: str, details: str = ""):
        super().__init__(message, error_code="BLENDER_RENDER_FAILED")
        self.details = details

class RenderJobNotFoundException(StudioDomainException):
    def __init__(self, job_id: str):
        super().__init__(
            f"Render görevi bulunamadı: '{job_id}'",
            error_code="RENDER_JOB_NOT_FOUND"
        )
        self.job_id = job_id

class InvalidRenderStateException(StudioDomainException):
    def __init__(self, message: str):
        super().__init__(message, error_code="INVALID_RENDER_STATE")

class AssetReferenceNotFoundException(StudioDomainException):
    def __init__(self, asset_id: str, details: str = ""):
        msg = f"SceneGraph tarafından referans verilen varlık bulunamadı: '{asset_id}'"
        if details:
            msg += f" ({details})"
        super().__init__(msg, error_code="ASSET_REFERENCE_NOT_FOUND")
        self.asset_id = asset_id

# ==========================================
# ElevenLabs & Voice Exceptions (Stage 4.4)
# ==========================================

class ElevenLabsException(StudioDomainException):
    def __init__(self, message: str, error_code: str = "ELEVENLABS_ERROR"):
        super().__init__(message, error_code=error_code)

class ElevenLabsNotConfiguredException(ElevenLabsException):
    def __init__(self, message: str = "ElevenLabs API anahtarı yapılandırılmamış. Lütfen .env dosyasına ELEVENLABS_API_KEY ekleyin."):
        super().__init__(message, error_code="ELEVENLABS_NOT_CONFIGURED")

class ElevenLabsApiException(ElevenLabsException):
    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        super().__init__(f"ElevenLabs API hatası ({status_code}): {message}", error_code="ELEVENLABS_API_ERROR")
        self.status_code = status_code
        self.details = details

class VoiceNotFoundException(ElevenLabsException):
    def __init__(self, voice_id: str):
        super().__init__(f"Ses profili (Voice ID) bulunamadı: '{voice_id}'", error_code="VOICE_NOT_FOUND")
        self.voice_id = voice_id

class AudioSynthesisException(ElevenLabsException):
    def __init__(self, message: str):
        super().__init__(message, error_code="AUDIO_SYNTHESIS_FAILED")


# ==========================================
# Video Composition Studio (Stage 4.5)
# ==========================================

class InvalidCompositionException(StudioDomainException):
    def __init__(self, message: str):
        super().__init__(message, error_code="INVALID_COMPOSITION")


class CompositionNotFoundException(StudioDomainException):
    def __init__(self, project_id: str):
        super().__init__(
            f"Proje için kompozisyon bulunamadı: '{project_id}'",
            error_code="COMPOSITION_NOT_FOUND",
        )
        self.project_id = project_id


class CompositionRenderException(StudioDomainException):
    def __init__(self, message: str, scene_id: Optional[str] = None, details: str = ""):
        super().__init__(message, error_code="COMPOSITION_RENDER_FAILED")
        self.scene_id = scene_id
        self.details = details


class CompositionFontException(StudioDomainException):
    def __init__(self, message: str):
        super().__init__(message, error_code="COMPOSITION_FONT_NOT_FOUND")


# ==========================================
# Phoneme / viseme lip sync (Stage 5.4)
# ==========================================

class InvalidAlignmentException(StudioDomainException):
    def __init__(self, message: str):
        super().__init__(message, error_code="INVALID_SPEECH_ALIGNMENT")


class AlignmentUnavailableException(StudioDomainException):
    """Raised when no provider can produce real alignment.

    This is an expected, reportable state rather than a crash: the caller falls
    back to the legacy mouth animation and labels it as such.
    """

    def __init__(self, message: str, details: str = ""):
        super().__init__(message, error_code="ALIGNMENT_UNAVAILABLE")
        self.details = details


class AlignmentProviderException(StudioDomainException):
    def __init__(self, message: str, details: str = ""):
        super().__init__(message, error_code="ALIGNMENT_PROVIDER_FAILED")
        self.details = details


