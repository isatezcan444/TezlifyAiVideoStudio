import os
import io
import pytest
import tempfile
import shutil
from tezlify_studio.infrastructure.media.local_media_storage import LocalMediaStorage
from tezlify_studio.domain.exceptions.media_exceptions import (
    MediaStorageException,
    InvalidMediaFileException,
)

@pytest.fixture
def storage():
    tmp_root = tempfile.mkdtemp()
    media_dir = os.path.join(tmp_root, "media")
    temp_dir = os.path.join(tmp_root, "temp")
    stor = LocalMediaStorage(media_dir, temp_dir)
    yield stor
    shutil.rmtree(tmp_root)

def test_storage_save_stream_and_hash(storage):
    payload = b"Sample video binary stream content 1234567890" * 100
    stream = io.BytesIO(payload)

    path, size, sha_hash = storage.save_stream(stream, "test_clip.mp4")

    assert os.path.exists(path)
    assert size == len(payload)
    assert len(sha_hash) == 64
    assert storage.get_file_size(path) == len(payload)

def test_storage_range_stream(storage):
    payload = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    stream = io.BytesIO(payload)
    path, size, _ = storage.save_stream(stream, "range_clip.mp4")

    # Request bytes from 5 to 14 (inclusive -> 10 bytes)
    chunks = list(storage.open_range_stream(path, start=5, end=14, chunk_size=4))
    sliced_bytes = b"".join(chunks)

    assert sliced_bytes == payload[5:15]
    assert len(sliced_bytes) == 10

def test_storage_max_bytes_enforcement(storage):
    payload = b"X" * 1024 * 50  # 50 KB
    stream = io.BytesIO(payload)

    # Max allowed: 10 KB
    with pytest.raises(InvalidMediaFileException) as exc:
        storage.save_stream(stream, "too_large.mp4", chunk_size=1024, max_bytes=10 * 1024)

    assert "Dosya boyutu sınırı aşıldı" in str(exc.value)

    # Verify temp dir is clean (no leftover temp files)
    temp_files = os.listdir(storage.temp_dir)
    assert len(temp_files) == 0

def test_storage_path_traversal_prevention(storage):
    safe_name = os.path.basename("../../etc/passwd.mp4")
    assert safe_name == "passwd.mp4"
