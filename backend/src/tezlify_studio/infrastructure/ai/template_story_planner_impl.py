import re
import uuid
from typing import Optional, List, Dict, Any
from tezlify_studio.application.ports.story_planner_port import StoryPlannerPort
from tezlify_studio.domain.value_objects.scene_graph import (
    SceneGraph,
    SceneResolution,
    SceneCharacter,
    CharacterStyle,
    StudioScene,
    SceneBackground,
    SceneCamera,
    CharacterPlacement,
    SceneDialogue,
    DialogueViseme,
    SceneTransition,
)
from tezlify_studio.domain.enums.studio_status import (
    CameraAngle,
    CameraMovement,
    CharacterPose,
    CharacterExpression,
    TransitionType,
    VisemeShape,
)

class TemplateStoryPlannerImpl(StoryPlannerPort):
    """
    Deterministic, offline-first story planner supporting rich Turkish prompts.
    Zero external API dependencies, zero network required.
    """

    SETTING_PRESETS: Dict[str, Dict[str, str]] = {
        "cafe": {"asset_id": "bg_modern_cafe", "lighting": "warm_interior"},
        "office": {"asset_id": "bg_office", "lighting": "daylight"},
        "park": {"asset_id": "bg_park", "lighting": "daylight"},
        "tech_studio": {"asset_id": "bg_tech_studio", "lighting": "neon_night"},
        "living_room": {"asset_id": "bg_living_room", "lighting": "warm_interior"},
    }

    CHARACTER_PAIRS: Dict[str, List[Dict[str, Any]]] = {
        "comedy": [
            {
                "id": "char_ali",
                "name": "Ali",
                "voice_id": "tr_male_ali",
                "style": {"hair_color": "#2C1810", "skin_tone": "#F5D0A9", "shirt_color": "#3B82F6", "pants_color": "#1E293B"}
            },
            {
                "id": "char_ayse",
                "name": "Ayşe",
                "voice_id": "tr_female_ayse",
                "style": {"hair_color": "#B45309", "skin_tone": "#FCE7D0", "shirt_color": "#EC4899", "pants_color": "#334155"}
            }
        ],
        "education": [
            {
                "id": "char_hoca",
                "name": "Prof. Bilge",
                "voice_id": "tr_male_bilge",
                "style": {"hair_color": "#64748B", "skin_tone": "#F5D0A9", "shirt_color": "#475569", "pants_color": "#0F172A"}
            },
            {
                "id": "char_deniz",
                "name": "Deniz",
                "voice_id": "tr_female_deniz",
                "style": {"hair_color": "#1E293B", "skin_tone": "#FCE7D0", "shirt_color": "#10B981", "pants_color": "#334155"}
            }
        ],
        "product": [
            {
                "id": "char_mert",
                "name": "Mert",
                "voice_id": "tr_male_mert",
                "style": {"hair_color": "#1F2937", "skin_tone": "#F5D0A9", "shirt_color": "#6366F1", "pants_color": "#111827"}
            },
            {
                "id": "char_selin",
                "name": "Selin",
                "voice_id": "tr_female_selin",
                "style": {"hair_color": "#D97706", "skin_tone": "#FDE68A", "shirt_color": "#F43F5E", "pants_color": "#374151"}
            }
        ],
        "story": [
            {
                "id": "char_efe",
                "name": "Efe",
                "voice_id": "tr_male_efe",
                "style": {"hair_color": "#451A03", "skin_tone": "#F5D0A9", "shirt_color": "#D97706", "pants_color": "#1C1917"}
            },
            {
                "id": "char_maya",
                "name": "Maya",
                "voice_id": "tr_female_maya",
                "style": {"hair_color": "#312E81", "skin_tone": "#FCE7D0", "shirt_color": "#8B5CF6", "pants_color": "#1E1B4B"}
            }
        ],
        "explainer": [
            {
                "id": "char_kaan",
                "name": "Kaan",
                "voice_id": "tr_male_kaan",
                "style": {"hair_color": "#18181B", "skin_tone": "#F5D0A9", "shirt_color": "#0EA5E9", "pants_color": "#27272A"}
            },
            {
                "id": "char_naz",
                "name": "Naz",
                "voice_id": "tr_female_naz",
                "style": {"hair_color": "#831843", "skin_tone": "#FCE7D0", "shirt_color": "#A855F7", "pants_color": "#3F3F46"}
            }
        ]
    }

    def plan_story(
        self,
        prompt: str,
        target_duration_seconds: Optional[float] = None,
        aspect_ratio: Optional[str] = "16:9",
        genre: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> SceneGraph:
        p_clean = prompt.strip()
        duration = self._extract_duration(p_clean, target_duration_seconds)
        ratio = self._extract_aspect_ratio(p_clean, aspect_ratio)
        detected_genre = self._extract_genre(p_clean, genre)
        setting = self._extract_setting(p_clean)
        proj_id = project_id or f"proj_{uuid.uuid4().hex[:8]}"

        resolution = self._build_resolution(ratio)
        characters = self._build_characters(p_clean, detected_genre)
        scenes = self._build_scenes(
            prompt=p_clean,
            duration=duration,
            genre=detected_genre,
            setting=setting,
            characters=characters,
        )

        title = self._generate_title(p_clean, detected_genre)

        scene_graph = SceneGraph(
            schema_version="1.0",
            project_id=proj_id,
            title=title,
            description=f"Otomatik oluşturulan {detected_genre} animasyonu: {p_clean[:120]}",
            resolution=resolution,
            characters=characters,
            scenes=scenes,
        )
        return scene_graph

    def _extract_duration(self, prompt: str, explicit: Optional[float]) -> float:
        if explicit and explicit > 0:
            return round(max(5.0, min(float(explicit), 300.0)), 1)

        # Regex search for duration in seconds or minutes
        sec_match = re.search(r'(\d+)\s*(saniye|sn|second|seconds|sec)', prompt, re.IGNORECASE)
        if sec_match:
            return float(sec_match.group(1))

        min_match = re.search(r'(\d+)\s*(dakika|dk|minute|minutes|min)', prompt, re.IGNORECASE)
        if min_match:
            return min(float(min_match.group(1)) * 60.0, 300.0)

        return 30.0  # Default duration

    def _extract_aspect_ratio(self, prompt: str, explicit: Optional[str]) -> str:
        if explicit in ("16:9", "9:16", "1:1"):
            return explicit

        p_lower = prompt.lower()
        if any(w in p_lower for w in ("shorts", "reels", "tiktok", "dikey", "portrait", "9:16")):
            return "9:16"
        if any(w in p_lower for w in ("kare", "square", "1:1", "instagram post")):
            return "1:1"
        return "16:9"

    def _extract_genre(self, prompt: str, explicit: Optional[str]) -> str:
        if explicit and explicit.lower() in self.CHARACTER_PAIRS:
            return explicit.lower()

        p_lower = prompt.lower()
        if any(w in p_lower for w in ("komik", "komedi", "şaka", "espiri", "kahkaha", "mizah", "gülünç", "funny", "comedy")):
            return "comedy"
        if any(w in p_lower for w in ("eğitim", "öğren", "öğret", "ders", "bilgi", "nasıl", "akademik", "education", "tutorial")):
            return "education"
        if any(w in p_lower for w in ("ürün", "tanıtım", "pazarlama", "özellik", "satış", "kampanya", "product", "promo")):
            return "product"
        if any(w in p_lower for w in ("açıkla", "açıklayıcı", "süreç", "kavram", "rehber", "infografik", "explainer")):
            return "explainer"
        if any(w in p_lower for w in ("hikaye", "öykü", "macera", "masal", "dram", "film", "story", "adventure")):
            return "story"

        return "comedy"

    def _extract_setting(self, prompt: str) -> Dict[str, str]:
        p_lower = prompt.lower()
        if any(w in p_lower for w in ("ofis", "iş", "şirket", "plaza", "toplantı", "office", "desk")):
            return self.SETTING_PRESETS["office"]
        if any(w in p_lower for w in ("park", "bahçe", "orman", "doğa", "sokak", "dışarı", "park", "garden")):
            return self.SETTING_PRESETS["park"]
        if any(w in p_lower for w in ("stüdyo", "laboratuvar", "bilim", "teknoloji", "kod", "studio", "lab")):
            return self.SETTING_PRESETS["tech_studio"]
        if any(w in p_lower for w in ("ev", "oda", "salon", "mutfak", "koltuk", "living room", "home")):
            return self.SETTING_PRESETS["living_room"]

        return self.SETTING_PRESETS["cafe"]

    def _build_resolution(self, ratio: str) -> SceneResolution:
        if ratio == "9:16":
            return SceneResolution(width=1080, height=1920, aspect_ratio="9:16", fps=30)
        elif ratio == "1:1":
            return SceneResolution(width=1080, height=1080, aspect_ratio="1:1", fps=30)
        return SceneResolution(width=1920, height=1080, aspect_ratio="16:9", fps=30)

    def _build_characters(self, prompt: str, genre: str) -> List[SceneCharacter]:
        raw_chars = self.CHARACTER_PAIRS.get(genre, self.CHARACTER_PAIRS["comedy"])
        result = []
        for c in raw_chars:
            style = CharacterStyle(**c["style"])
            result.append(
                SceneCharacter(
                    id=c["id"],
                    name=c["name"],
                    voice_id=c["voice_id"],
                    style=style,
                )
            )
        return result

    def _generate_title(self, prompt: str, genre: str) -> str:
        words = prompt.split()
        if len(words) <= 5:
            clean = " ".join(words).strip(".,!?:;")
            return clean.capitalize() if clean else f"Tezlify {genre.capitalize()} Animasyonu"
        genre_titles = {
            "comedy": "Kafede Neşeli Sohbet",
            "education": "Pratik Bilgiler Atölyesi",
            "product": "Geleceğin Akıllı Çözümü",
            "story": "Bilinmeyene Doğru Yolculuk",
            "explainer": "Adım Adım Kolay Rehber",
        }
        return genre_titles.get(genre, "Tezlify AI Animasyon Projesi")

    def _build_scenes(
        self,
        prompt: str,
        duration: float,
        genre: str,
        setting: Dict[str, str],
        characters: List[SceneCharacter],
    ) -> List[StudioScene]:
        # Divide total duration into scenes
        num_scenes = 1 if duration <= 15.0 else (2 if duration <= 35.0 else 3)
        scene_durations = [round(duration / num_scenes, 1)] * num_scenes
        # Adjust remainder to match exact duration
        scene_durations[-1] = round(duration - sum(scene_durations[:-1]), 1)

        char_a = characters[0]
        char_b = characters[1] if len(characters) > 1 else characters[0]

        dialogue_bank = self._get_dialogue_templates(genre)

        scenes = []
        for i, sc_dur in enumerate(scene_durations):
            seq = i + 1
            scene_id = f"scene_{seq:02d}"
            bg = SceneBackground(
                type="preset",
                asset_id=setting["asset_id"],
                lighting=setting["lighting"],
            )

            # Alternate camera dynamics
            cam_angles = [CameraAngle.WIDE_SHOT, CameraAngle.TWO_SHOT, CameraAngle.CLOSE_UP]
            cam_moves = [CameraMovement.STATIC, CameraMovement.SLOW_PAN_RIGHT, CameraMovement.SLOW_ZOOM_IN]
            cam = SceneCamera(
                angle=cam_angles[i % len(cam_angles)],
                fov=45.0,
                movement=cam_moves[i % len(cam_moves)],
            )

            # Placements
            placements = [
                CharacterPlacement(
                    character_id=char_a.id,
                    position=[-1.2, 0.0, 0.0],
                    rotation_y=20.0,
                    pose=CharacterPose.STANDING if i % 2 == 0 else CharacterPose.GESTURING,
                    expression=CharacterExpression.CHEERFUL if i % 2 == 0 else CharacterExpression.NEUTRAL,
                ),
                CharacterPlacement(
                    character_id=char_b.id,
                    position=[1.2, 0.0, 0.0],
                    rotation_y=-20.0,
                    pose=CharacterPose.SITTING_TABLE if i % 2 == 0 else CharacterPose.POINTING,
                    expression=CharacterExpression.SURPRISED if i % 2 == 0 else CharacterExpression.THINKING,
                ),
            ]

            # Dialogues for this scene
            scene_dialogues = []
            pool = dialogue_bank[i % len(dialogue_bank)]
            
            # Dialogue 1: Character A
            d1_text = pool["a"]
            d1_start = 1.0
            d1_dur = round(min(5.5, max(2.5, (sc_dur - 3.0) / 2)), 1)
            d1_end = round(d1_start + d1_dur, 1)

            visemes_1 = self._generate_dummy_visemes(d1_dur)
            scene_dialogues.append(
                SceneDialogue(
                    character_id=char_a.id,
                    start_time=d1_start,
                    end_time=d1_end,
                    text=d1_text,
                    visemes=visemes_1,
                )
            )

            # Dialogue 2: Character B (if scene duration permits)
            if sc_dur >= 7.0 and len(characters) > 1:
                d2_text = pool["b"]
                d2_start = round(d1_end + 0.5, 1)
                d2_dur = round(min(5.5, max(2.0, sc_dur - d2_start - 0.5)), 1)
                d2_end = round(min(sc_dur - 0.2, d2_start + d2_dur), 1)

                if d2_end > d2_start:
                    visemes_2 = self._generate_dummy_visemes(d2_end - d2_start)
                    scene_dialogues.append(
                        SceneDialogue(
                            character_id=char_b.id,
                            start_time=d2_start,
                            end_time=d2_end,
                            text=d2_text,
                            visemes=visemes_2,
                        )
                    )

            transition = None
            if i < num_scenes - 1:
                transition = SceneTransition(type=TransitionType.CROSSFADE, duration_seconds=0.5)

            scenes.append(
                StudioScene(
                    scene_id=scene_id,
                    sequence_order=seq,
                    duration_seconds=sc_dur,
                    background=bg,
                    camera=cam,
                    character_placements=placements,
                    dialogues=scene_dialogues,
                    transition=transition,
                )
            )

        return scenes

    def _generate_dummy_visemes(self, duration: float) -> List[DialogueViseme]:
        shapes = [VisemeShape.X, VisemeShape.A, VisemeShape.B, VisemeShape.C, VisemeShape.E, VisemeShape.O]
        step = 0.35
        current = 0.0
        visemes = []
        idx = 0
        while current < duration:
            visemes.append(DialogueViseme(time=round(current, 2), shape=shapes[idx % len(shapes)]))
            current += step
            idx += 1
        visemes.append(DialogueViseme(time=round(duration, 2), shape=VisemeShape.X))
        return visemes

    def _get_dialogue_templates(self, genre: str) -> List[Dict[str, str]]:
        banks = {
            "comedy": [
                {
                    "a": "Selam! Kahve makinesini nihayet tamir edebildin mi?",
                    "b": "Tamir ettim sayılır, artık kahve yerine doğrudan süt köpüğü fırlatıyor!"
                },
                {
                    "a": "Peki ya sipariş ettiğin yedek parça nerede?",
                    "b": "Kargocu arkadaş onu kedi maması sanıp komşuya teslim etmiş!"
                },
                {
                    "a": "Görünüşe göre bugün kahvemizi başka yerde içeceğiz!",
                    "b": "Kesinlikle, en azından orada köpük yağmuru yok!"
                }
            ],
            "education": [
                {
                    "a": "Bugün yapay zeka ve animasyonun nasıl birleştiğini inceliyoruz.",
                    "b": "Harika bir konu! Kod blokları ve rig mekaniği nasıl senkron oluyor?"
                },
                {
                    "a": "Scene Graph JSON sayesinde tüm sahne parametreleri önceden hesaplanıyor.",
                    "b": "Böylece render motoru her kareyi kusursuz zamanlamayla işleyebiliyor."
                },
                {
                    "a": "İşte bu sistem modern stüdyo üretimini onlarca kat hızlandırıyor.",
                    "b": "Geleceğin animatörleri için olağanüstü bir araç!"
                }
            ],
            "product": [
                {
                    "a": "Video üretmek için günlerce uğraşmaktan sıkılmadınız mı?",
                    "b": "Evet! Hızlı, pratik ve profesyonel bir stüdyo yazılımı arıyordum."
                },
                {
                    "a": "Tezlify AI Video Studio ile sadece fikrinizi yazarak animasyon üretebilirsiniz.",
                    "b": "Üstelik tek tıkla doğrudan YouTube kanalınıza yayınlanıyor!"
                },
                {
                    "a": "Hemen şimdi deneyin, video üretiminizi baştan yaratın.",
                    "b": "Geleceğin stüdyosu artık parmaklarınızın ucunda!"
                }
            ],
            "story": [
                {
                    "a": "Eski haritadaki işaret tam olarak bu antik geçidi gösteriyordu.",
                    "b": "Emin misin? Yıllardır buraya kimsenin adım attığı görülmemiş."
                },
                {
                    "a": "İşte kapıdaki gizemli sembol! Sırlar sonunda açığa çıkıyor.",
                    "b": "O zaman meşaleyi yak ve dikkatli ol, macera yeni başlıyor."
                },
                {
                    "a": "Adımlarını izle, ardımızdaki sis giderek yoğunlaşıyor.",
                    "b": "Korkma, bu yolculuğun sonunda beklediğimiz yanıtlar var."
                }
            ],
            "explainer": [
                {
                    "a": "İlk adımda sahne planınızı ve karakterlerinizi belirleyin.",
                    "b": "Karakterlerin renkleri ve pozları kolayca özelleştirilebiliyor mu?"
                },
                {
                    "a": "Elbette, stil ve açılar tamamen kullanıcı kontrolündedir.",
                    "b": "Sonraki aşamada ise seslendirme ve dudak senkronizasyonu devreye giriyor."
                },
                {
                    "a": "Tamamlanan proje yüksek kaliteli 1080p video olarak derlenir.",
                    "b": "İşte dakikalar içinde hazır profesyonel animasyon!"
                }
            ]
        }
        return banks.get(genre, banks["comedy"])
