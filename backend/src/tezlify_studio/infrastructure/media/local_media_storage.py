import os
import hashlib
import shutil
from typing import BinaryIO, Generator, Tuple, Optional
from tezlify_studio.application.ports.media_storage_port import MediaStoragePort
from tezlify_studio.domain.exceptions.media_exceptions import (
    MediaStorageException,
    InvalidMediaFileException,
)

class LocalMediaStorage(MediaStoragePort):
    def __init__(self, media_dir: str, temp_dir: str):
        self.media_dir = os.path.abspath(media_dir)
        self.temp_dir = os.path.abspath(temp_dir)
        os.makedirs(self.media_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)

    def _sanitize_path(self, base_dir: str, filename: str) -> str:
        safe_name = os.path.basename(filename)
        dest_path = os.path.abspath(os.path.join(base_dir, safe_name))
        if not dest_path.startswith(base_dir):
            raise MediaStorageException(f"Path traversal detected for filename: {filename}")
        return dest_path

    def save_stream(
        self,
        stream: BinaryIO,
        destination_filename: str,
        chunk_size: int = 1024 * 1024,
        max_bytes: Optional[int] = None,
    ) -> Tuple[str, int, str]:
        temp_path = os.path.join(self.temp_dir, f"temp_{os.path.basename(destination_filename)}")
        dest_path = self._sanitize_path(self.media_dir, destination_filename)

        hasher = hashlib.sha256()
        total_size = 0

        try:
            with open(temp_path, "wb") as f_out:
                while True:
                    chunk = stream.read(chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    total_size += len(chunk)
                    if max_bytes and total_size > max_bytes:
                        limit_mb = round(max_bytes / (1024 * 1024), 1)
                        raise InvalidMediaFileException(
                            f"Dosya boyutu sınırı aşıldı (İzin verilen maksimum: {limit_mb} MB)."
                        )
                    f_out.write(chunk)

            # Move atomically from temp to final destination
            shutil.move(temp_path, dest_path)
            return dest_path, total_size, hasher.hexdigest()

        except InvalidMediaFileException:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise MediaStorageException(f"Failed to stream and save media: {str(e)}")

    def get_file_size(self, file_path: str) -> int:
        if not os.path.exists(file_path):
            return 0
        return os.path.getsize(file_path)

    def exists(self, file_path: str) -> bool:
        return os.path.exists(file_path)

    def delete_file(self, file_path: str) -> bool:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except OSError as e:
            raise MediaStorageException(f"Failed to delete file {file_path}: {str(e)}")

    def open_range_stream(
        self,
        file_path: str,
        start: int,
        end: int,
        chunk_size: int = 1024 * 512
    ) -> Generator[bytes, None, None]:
        if not os.path.exists(file_path):
            raise MediaStorageException(f"File not found: {file_path}")

        with open(file_path, "rb") as f:
            f.seek(start)
            bytes_left = (end - start) + 1
            while bytes_left > 0:
                current_chunk = min(chunk_size, bytes_left)
                data = f.read(current_chunk)
                if not data:
                    break
                bytes_left -= len(data)
                yield data

