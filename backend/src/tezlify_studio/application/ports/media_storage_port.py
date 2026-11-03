from abc import ABC, abstractmethod
from typing import BinaryIO, Generator, Tuple, Optional

class MediaStoragePort(ABC):
    @abstractmethod
    def save_stream(
        self,
        stream: BinaryIO,
        destination_filename: str,
        chunk_size: int = 1024 * 1024,
        max_bytes: Optional[int] = None,
    ) -> Tuple[str, int, str]:
        """
        Saves a streaming upload to permanent storage.
        Returns: (absolute_file_path, total_size_bytes, sha256_hash)
        """
        pass

    @abstractmethod
    def get_file_size(self, file_path: str) -> int:
        pass

    @abstractmethod
    def exists(self, file_path: str) -> bool:
        pass

    @abstractmethod
    def delete_file(self, file_path: str) -> bool:
        pass

    @abstractmethod
    def open_range_stream(
        self,
        file_path: str,
        start: int,
        end: int,
        chunk_size: int = 1024 * 512
    ) -> Generator[bytes, None, None]:
        """
        Generator yielding bytes for HTTP Range requests.
        """
        pass

