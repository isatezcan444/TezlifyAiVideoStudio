from tezlify_studio.application.ports.character_repository_port import CharacterRepositoryPort
from tezlify_studio.domain.exceptions.studio_exceptions import (
    CharacterNotFoundException,
    StudioDomainException,
)

class DeleteCharacterUseCase:
    def __init__(self, char_repo: CharacterRepositoryPort):
        self.char_repo = char_repo

    def execute(self, character_id: str) -> bool:
        character = self.char_repo.get_by_id(character_id)
        if not character:
            raise CharacterNotFoundException(character_id)

        # Do not hard delete built-in characters
        if character.is_builtin:
            raise StudioDomainException(
                f"Sistem yerleşik karakteri '{character.name}' silinemez.",
                error_code="BUILTIN_CHARACTER_PROTECTED"
            )

        return self.char_repo.delete(character_id)
