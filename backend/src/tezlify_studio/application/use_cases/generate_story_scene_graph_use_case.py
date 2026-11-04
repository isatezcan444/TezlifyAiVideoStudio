from typing import Optional
from tezlify_studio.application.ports.story_planner_port import StoryPlannerPort
from tezlify_studio.application.dto.studio_dto import GenerateStoryRequestDTO
from tezlify_studio.domain.value_objects.scene_graph import SceneGraph

class GenerateStorySceneGraphUseCase:
    def __init__(
        self,
        template_planner: StoryPlannerPort,
        ollama_planner: Optional[StoryPlannerPort] = None,
    ):
        self.template_planner = template_planner
        self.ollama_planner = ollama_planner

    def execute(self, req: GenerateStoryRequestDTO) -> SceneGraph:
        clean_prompt = req.prompt.strip()
        if not clean_prompt:
            raise ValueError("Senaryo promptu boş olamaz.")

        provider = (req.provider or "auto").lower()

        planner: StoryPlannerPort
        if provider == "template":
            planner = self.template_planner
        elif provider == "ollama" and self.ollama_planner:
            planner = self.ollama_planner
        else:
            # "auto": prefer ollama if configured, fallback handled inside ollama planner
            planner = self.ollama_planner if self.ollama_planner else self.template_planner

        scene_graph = planner.plan_story(
            prompt=clean_prompt,
            target_duration_seconds=req.target_duration_seconds,
            aspect_ratio=req.aspect_ratio or "16:9",
            genre=req.genre,
        )

        return scene_graph
