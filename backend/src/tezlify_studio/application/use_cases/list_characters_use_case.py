from typing import List, Tuple, Optional
from tezlify_studio.application.ports.character_repository_port import CharacterRepositoryPort
from tezlify_studio.application.dto.character_dto import CharacterDTO
from tezlify_studio.application.dto.mappers import character_to_dto

class ListCharactersUseCase:
    def __init__(self, char_repo: CharacterRepositoryPort):
        self.char_repo = char_repo

    def execute(
        self,
        limit: int = 50,
        offset: int = 0,
        gender: Optional[str] = None,
        is_builtin: Optional[bool] = None,
    ) -> Tuple[List[CharacterDTO], int]:
        total = self.char_repo.count(gender=gender, is_builtin=is_builtin)
        characters = self.char_repo.list_characters(
            limit=limit,
            offset=offset,
            gender=gender,
            is_builtin=is_builtin,
        )
        return [character_to_dto(c) for c in characters], total
