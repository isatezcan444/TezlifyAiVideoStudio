from tezlify_studio.application.ports.character_repository_port import CharacterRepositoryPort
from tezlify_studio.application.dto.character_dto import CharacterDTO
from tezlify_studio.application.dto.mappers import character_to_dto
from tezlify_studio.domain.exceptions.studio_exceptions import CharacterNotFoundException

class GetCharacterUseCase:
    def __init__(self, char_repo: CharacterRepositoryPort):
        self.char_repo = char_repo

    def execute(self, character_id: str) -> CharacterDTO:
        character = self.char_repo.get_by_id(character_id)
        if not character:
            raise CharacterNotFoundException(character_id)
        return character_to_dto(character)
