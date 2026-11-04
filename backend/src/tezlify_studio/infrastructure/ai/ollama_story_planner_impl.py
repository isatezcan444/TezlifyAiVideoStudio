import json
import logging
import re
from typing import Optional, List, Dict, Any
import httpx

from tezlify_studio.application.ports.story_planner_port import StoryPlannerPort
from tezlify_studio.domain.value_objects.scene_graph import SceneGraph
from tezlify_studio.infrastructure.ai.template_story_planner_impl import TemplateStoryPlannerImpl

logger = logging.getLogger(__name__)

class OllamaStoryPlannerImpl(StoryPlannerPort):
    """
    Optional Ollama local LLM adapter with safe automatic fallback to TemplateStoryPlannerImpl.
    Guarantees that network errors, model absence, or malformed JSON never crash the application.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        timeout_seconds: float = 30.0,
        fallback_planner: Optional[StoryPlannerPort] = None,
        http_client: Optional[httpx.Client] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.fallback = fallback_planner or TemplateStoryPlannerImpl()
        self._client = http_client or httpx.Client(timeout=timeout_seconds)

    def is_available(self) -> bool:
        """Checks if local Ollama server is running and reachable."""
        try:
            resp = self._client.get(f"{self.base_url}/api/tags", timeout=2.0)
            return resp.status_code == 200
        except Exception:
            return False

    def list_installed_models(self) -> List[str]:
        """Lists names of models currently downloaded in local Ollama."""
        try:
            resp = self._client.get(f"{self.base_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception as e:
            logger.debug("Failed to list Ollama models: %s", e)
        return []

    def plan_story(
        self,
        prompt: str,
        target_duration_seconds: Optional[float] = None,
        aspect_ratio: Optional[str] = "16:9",
        genre: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> SceneGraph:
        """
        Attempts to generate SceneGraph via Ollama.
        If unavailable, timed out, or returning invalid schema, falls back seamlessly to TemplateStoryPlanner.
        """
        # 1. Quick availability check
        if not self.is_available():
            logger.info("Ollama is not running at %s. Falling back to TemplateStoryPlanner.", self.base_url)
            return self.fallback.plan_story(
                prompt=prompt,
                target_duration_seconds=target_duration_seconds,
                aspect_ratio=aspect_ratio,
                genre=genre,
                project_id=project_id,
            )

        # 2. Build system instructions and schema requirements
        system_prompt = self._build_system_prompt(target_duration_seconds, aspect_ratio)
        user_prompt = f"Senaryo İsteği: {prompt}\nTür: {genre or 'Otomatik'}"

        # 3. Call Ollama API with max 1 retry for JSON formatting
        for attempt in range(2):
            try:
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {
                        "temperature": 0.4,
                        "num_predict": 1500,
                    },
                }

                resp = self._client.post(f"{self.base_url}/api/chat", json=payload)
                if resp.status_code != 200:
                    logger.warning("Ollama returned HTTP %d: %s", resp.status_code, resp.text)
                    break

                raw_content = resp.json().get("message", {}).get("content", "")
                parsed_json = self._extract_json_dict(raw_content)

                if parsed_json:
                    # Enforce project_id and schema_version
                    parsed_json["schema_version"] = "1.0"
                    if project_id and not parsed_json.get("project_id"):
                        parsed_json["project_id"] = project_id

                    # Validate strictly with Pydantic SceneGraph
                    scene_graph = SceneGraph.model_validate(parsed_json)
                    logger.info("Successfully generated SceneGraph via Ollama (%s)", self.model)
                    return scene_graph

            except Exception as e:
                logger.warning("Ollama generation attempt %d failed: %s", attempt + 1, e)

        # 4. Fallback if LLM generation was incomplete or invalid
        logger.info("Ollama output invalid or failed. Gracefully falling back to TemplateStoryPlanner.")
        return self.fallback.plan_story(
            prompt=prompt,
            target_duration_seconds=target_duration_seconds,
            aspect_ratio=aspect_ratio,
            genre=genre,
            project_id=project_id,
        )

    def _extract_json_dict(self, text: str) -> Optional[Dict[str, Any]]:
        """Cleans and extracts JSON object from LLM response text."""
        clean_text = text.strip()
        # Remove markdown code blocks if present
        clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
        clean_text = re.sub(r"\s*```$", "", clean_text)

        try:
            return json.loads(clean_text)
        except Exception:
            # Try to find outermost { ... }
            match = re.search(r"(\{.*\})", clean_text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
        return None

    def _build_system_prompt(self, duration: Optional[float], aspect_ratio: Optional[str]) -> str:
        dur = duration or 30.0
        ratio = aspect_ratio or "16:9"
        w, h = (1080, 1920) if ratio == "9:16" else ((1080, 1080) if ratio == "1:1" else (1920, 1080))
        return (
            "Sen profesyonel bir 2D animasyon yönetmenisin. Kullanıcının isteğini SceneGraph JSON nesnesine dönüştür.\n"
            "Yanıtın SADECE geçerli bir JSON nesnesi olmalı, ek açıklama veya markdown yazma.\n"
            "JSON şeması kuralları:\n"
            "- schema_version: '1.0'\n"
            "- project_id: string (örn: 'proj_ai_01')\n"
            "- title: string (boş olamaz)\n"
            "- description: string\n"
            f"- resolution: {{ 'width': {w}, 'height': {h}, 'aspect_ratio': '{ratio}', 'fps': 30 }}\n"
            "- characters: en az 1 karakter. [{{ 'id': 'char_1', 'name': 'Ad', 'voice_id': 'tr_yelda', "
            "'style': {{ 'hair_color': '#2C1810', 'skin_tone': '#F5D0A9', 'shirt_color': '#3B82F6', 'pants_color': '#1E293B' }} }}]\n"
            f"- scenes: toplam süre yaklaşık {dur} saniye olacak şekilde en az 1 sahne. Her sahne için:\n"
            "  * scene_id: benzersiz string ('scene_01')\n"
            "  * sequence_order: integer\n"
            "  * duration_seconds: float (örn: 15.0)\n"
            "  * background: {{ 'type': 'preset', 'asset_id': 'bg_modern_cafe', 'lighting': 'warm_interior' }}\n"
            "  * camera: {{ 'angle': 'medium_shot', 'fov': 45.0, 'movement': 'static' }}\n"
            "  * character_placements: her karakter için [x, y, z] pozisyon, rotation_y, pose ('standing'|'sitting_table'|'gesturing'), expression ('neutral'|'cheerful'|'surprised')\n"
            "  * dialogues: her diyalog için character_id, start_time (>=0), end_time (>start_time ve <=duration_seconds), text (Türkçe)"
        )
