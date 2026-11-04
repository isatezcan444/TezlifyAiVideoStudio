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
