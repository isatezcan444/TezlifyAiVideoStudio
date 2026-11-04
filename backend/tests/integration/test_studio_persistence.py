import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tezlify_studio.infrastructure.persistence.models.media_models import Base
from tezlify_studio.infrastructure.persistence.models.studio_models import StudioProjectModel  # registers table
from tezlify_studio.infrastructure.persistence.repositories.studio_project_repository_impl import StudioProjectRepositoryImpl
from tezlify_studio.domain.entities.studio_project import StudioProject
from tezlify_studio.domain.enums.studio_status import StudioProjectStatus
from tezlify_studio.infrastructure.ai.template_story_planner_impl import TemplateStoryPlannerImpl

@pytest.fixture
def studio_repo():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    repository = StudioProjectRepositoryImpl(session)
    yield repository
    session.close()

def test_studio_project_save_and_get(studio_repo):
    planner = TemplateStoryPlannerImpl()
    sg = planner.plan_story("Test animasyon projesi 30 saniye", project_id="proj_save_1")

    project = StudioProject(
        id="proj_save_1",
        title=sg.title,
        description=sg.description,
        status=StudioProjectStatus.DRAFT,
        scene_graph=sg,
    )

    saved = studio_repo.save(project)
    assert saved.id == "proj_save_1"
    assert saved.title == sg.title
    assert saved.status == StudioProjectStatus.DRAFT
    assert saved.scene_graph is not None
    assert saved.scene_graph.schema_version == "1.0"
    assert len(saved.scene_graph.scenes) >= 2

    fetched = studio_repo.get_by_id("proj_save_1")
    assert fetched is not None
    assert fetched.id == "proj_save_1"
    assert fetched.title == sg.title
    assert fetched.scene_graph is not None
    assert fetched.scene_graph.title == sg.title

def test_studio_project_list_pagination_and_filter(studio_repo):
    for i in range(5):
        status = StudioProjectStatus.DRAFT if i % 2 == 0 else StudioProjectStatus.SCENARIO_READY
        p = StudioProject(
            id=f"proj_{i}",
            title=f"Project {i}",
            description=f"Desc {i}",
            status=status,
            scene_graph=None,
        )
        studio_repo.save(p)

    assert studio_repo.count_projects() == 5
    assert studio_repo.count_projects(status=StudioProjectStatus.DRAFT) == 3
    assert studio_repo.count_projects(status=StudioProjectStatus.SCENARIO_READY) == 2

    # Test limit and offset
    page1 = studio_repo.list_projects(limit=2, offset=0)
    assert len(page1) == 2

    page2 = studio_repo.list_projects(limit=2, offset=2)
    assert len(page2) == 2
    assert page1[0].id != page2[0].id

    # Test filter by status
    drafts = studio_repo.list_projects(status=StudioProjectStatus.DRAFT)
    assert len(drafts) == 3
    assert all(d.status == StudioProjectStatus.DRAFT for d in drafts)

def test_studio_project_update(studio_repo):
    p = StudioProject(
        id="proj_update_1",
        title="Original Title",
        description="Original Desc",
        status=StudioProjectStatus.DRAFT,
    )
    studio_repo.save(p)

    # Fetch and update
    fetched = studio_repo.get_by_id("proj_update_1")
    assert fetched is not None
    fetched.update_metadata(title="Updated Title", description="Updated Desc")
    fetched.transition_to(StudioProjectStatus.SCENARIO_READY)
    updated = studio_repo.save(fetched)

    assert updated.title == "Updated Title"
    assert updated.description == "Updated Desc"
    assert updated.status == StudioProjectStatus.SCENARIO_READY

    # Verify persisted in database
    refetched = studio_repo.get_by_id("proj_update_1")
    assert refetched.title == "Updated Title"
    assert refetched.status == StudioProjectStatus.SCENARIO_READY

def test_studio_project_delete(studio_repo):
    p = StudioProject(
        id="proj_del_1",
        title="To Delete",
        description="Will be deleted",
        status=StudioProjectStatus.DRAFT,
    )
    studio_repo.save(p)
    assert studio_repo.count_projects() == 1

    deleted = studio_repo.delete("proj_del_1")
    assert deleted is True
    assert studio_repo.get_by_id("proj_del_1") is None
    assert studio_repo.count_projects() == 0

    # Delete non-existent
    assert studio_repo.delete("non_existent_id") is False
