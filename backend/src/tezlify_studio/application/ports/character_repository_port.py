from abc import ABC, abstractmethod
from typing import List, Optional
from tezlify_studio.domain.entities.character import Character

class CharacterRepositoryPort(ABC):
    @abstractmethod
    def save(self, character: Character) -> Character:
        pass

    @abstractmethod
    def get_by_id(self, character_id: str) -> Optional[Character]:
        pass

    @abstractmethod
    def list_characters(
        self,
        limit: int = 50,
        offset: int = 0,
        gender: Optional[str] = None,
        is_builtin: Optional[bool] = None,
    ) -> List[Character]:
        pass

    @abstractmethod
    def count(self, gender: Optional[str] = None, is_builtin: Optional[bool] = None) -> int:
        pass

    @abstractmethod
    def delete(self, character_id: str) -> bool:
        pass
