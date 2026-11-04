import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tezlify_studio.infrastructure.persistence.models.media_models import Base
from tezlify_studio.infrastructure.persistence.models.studio_models import CharacterModel, StudioAssetModel
from tezlify_studio.infrastructure.persistence.repositories.character_repository_impl import CharacterRepositoryImpl
from tezlify_studio.infrastructure.persistence.repositories.studio_asset_repository_impl import StudioAssetRepositoryImpl
from tezlify_studio.domain.entities.character import Character
from tezlify_studio.domain.entities.studio_asset import StudioAsset
from tezlify_studio.domain.enums.studio_status import (
    AssetCategory,
    AssetFormat,
    CharacterPose,
    CharacterExpression,
    HairStyle,
)
from tezlify_studio.domain.value_objects.character_models import CharacterColorPalette, BodyProportions

@pytest.fixture
def char_repo():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield CharacterRepositoryImpl(session)
    session.close()

@pytest.fixture
def asset_repo():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield StudioAssetRepositoryImpl(session)
    session.close()

def test_character_crud_lifecycle(char_repo):
    char = Character(
        id="char_persist_1",
        name="Persist Ali",
        description="Test description",
        gender="male",
        palette=CharacterColorPalette(shirt_color="#3B82F6"),
        hair_style=HairStyle.SHORT_PARTED.value,
        default_expression=CharacterExpression.CHEERFUL,
        default_pose=CharacterPose.STANDING,
        is_builtin=False,
    )

    # 1. Save
    saved = char_repo.save(char)
    assert saved.id == "char_persist_1"
    assert saved.name == "Persist Ali"
    assert saved.palette.shirt_color == "#3B82F6"

    # 2. Get by ID
    fetched = char_repo.get_by_id("char_persist_1")
    assert fetched is not None
    assert fetched.name == "Persist Ali"
    assert fetched.default_expression == CharacterExpression.CHEERFUL

    # 3. Update
    fetched.update_profile(name="Persist Ali Renamed")
    fetched.update_appearance(palette=CharacterColorPalette(shirt_color="#10B981"))
    updated = char_repo.save(fetched)
    assert updated.name == "Persist Ali Renamed"
    assert updated.palette.shirt_color == "#10B981"

    # 4. List and count
    assert char_repo.count() == 1
    assert char_repo.count(gender="male") == 1
    assert char_repo.count(gender="female") == 0
    all_chars = char_repo.list_characters()
    assert len(all_chars) == 1

    # 5. Delete
    assert char_repo.delete("char_persist_1") is True
    assert char_repo.get_by_id("char_persist_1") is None
    assert char_repo.count() == 0

def test_studio_asset_crud_lifecycle(asset_repo):
    asset = StudioAsset(
        id="bg_persist_cafe",
        name="Persist Cafe",
        category=AssetCategory.BACKGROUND,
        description="Cafe description",
        file_path="/path/to/cafe.blend",
        asset_format=AssetFormat.BLEND,
        thumbnail_path="/path/to/cafe.png",
        tags=["cafe", "warm"],
        is_builtin=True,
    )

    # 1. Save
    saved = asset_repo.save(asset)
    assert saved.id == "bg_persist_cafe"
    assert saved.category == AssetCategory.BACKGROUND
    assert "cafe" in saved.tags

    # 2. Get by ID
    fetched = asset_repo.get_by_id("bg_persist_cafe")
    assert fetched is not None
    assert fetched.name == "Persist Cafe"
    assert fetched.file_path == "/path/to/cafe.blend"

    # 3. List by category
    bg_list = asset_repo.list_assets(category=AssetCategory.BACKGROUND)
    assert len(bg_list) == 1
    prop_list = asset_repo.list_assets(category=AssetCategory.PROP)
    assert len(prop_list) == 0

    # 4. Count
    assert asset_repo.count() == 1
    assert asset_repo.count(category=AssetCategory.BACKGROUND) == 1
    assert asset_repo.count(category=AssetCategory.PROP) == 0

    # 5. Delete
    assert asset_repo.delete("bg_persist_cafe") is True
    assert asset_repo.get_by_id("bg_persist_cafe") is None
    assert asset_repo.count() == 0
