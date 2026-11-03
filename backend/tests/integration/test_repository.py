import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tezlify_studio.infrastructure.persistence.models.media_models import Base
from tezlify_studio.infrastructure.persistence.repositories.media_repository_impl import MediaRepositoryImpl
from tezlify_studio.domain.entities.media_asset import MediaAsset
from tezlify_studio.domain.value_objects.video_metadata import VideoMetadata
from tezlify_studio.domain.enums.media_status import MediaStatus

@pytest.fixture
def repo():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    repository = MediaRepositoryImpl(session)
    yield repository
    session.close()

def test_repository_save_and_get(repo):
    asset = MediaAsset(
        id="repo-test-1",
        filename="clip1.mp4",
        original_filename="original_clip.mp4",
        file_path="/data/media/clip1.mp4",
        file_size_bytes=4096,
        mime_type="video/mp4",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        status=MediaStatus.READY,
        metadata=VideoMetadata(
            duration_seconds=30.0,
            width=1280,
            height=720,
            fps=25.0,
            video_codec="h264",
            audio_codec="aac",
            aspect_ratio="1.78:1",
        ),
    )

    saved = repo.save(asset)
    assert saved.id == "repo-test-1"

    fetched = repo.get_by_id("repo-test-1")
    assert fetched is not None
    assert fetched.original_filename == "original_clip.mp4"
    assert fetched.metadata.width == 1280

    by_hash = repo.get_by_hash(asset.sha256_hash)
    assert by_hash is not None
    assert by_hash.id == "repo-test-1"

    all_assets = repo.list_all()
    assert len(all_assets) == 1
    assert repo.count() == 1

    deleted = repo.delete("repo-test-1")
    assert deleted is True
    assert repo.get_by_id("repo-test-1") is None
    assert repo.count() == 0
