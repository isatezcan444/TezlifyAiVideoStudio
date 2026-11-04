import os
import logging
from typing import Optional
from tezlify_studio.application.ports.character_repository_port import CharacterRepositoryPort
from tezlify_studio.application.ports.studio_asset_repository_port import StudioAssetRepositoryPort
from tezlify_studio.application.ports.blender_asset_generator_port import BlenderAssetGeneratorPort
from tezlify_studio.domain.entities.character import Character
from tezlify_studio.domain.entities.studio_asset import StudioAsset
from tezlify_studio.domain.enums.studio_status import (
    AssetCategory,
    AssetFormat,
    CharacterPose,
    CharacterExpression,
    HairStyle,
    EyeStyle,
    ClothingStyle,
)
from tezlify_studio.domain.value_objects.character_models import CharacterColorPalette, BodyProportions
from tezlify_studio.infrastructure.configuration.settings import settings

logger = logging.getLogger(__name__)

class SeedBuiltinAssetsUseCase:
    def __init__(
        self,
        char_repo: CharacterRepositoryPort,
        asset_repo: StudioAssetRepositoryPort,
        blender_gen: Optional[BlenderAssetGeneratorPort] = None,
    ):
        self.char_repo = char_repo
        self.asset_repo = asset_repo
        self.blender_gen = blender_gen

    def execute(self) -> None:
        base_assets_dir = os.path.join(settings.resolved_data_dir, "studio_assets")

        # 1. Built-in Characters: Ali & Ayşe
        builtin_chars = [
            Character(
                id="char_ali",
                name="Ali",
                description="Genç, enerjik ve mizahi erkek karakter. Mavi üst, koyu pantolon ve kısa siyah saç.",
                gender="male",
                palette=CharacterColorPalette(
                    skin_tone="#F5D0A9",
                    hair_color="#2C1810",
                    eye_color="#1E293B",
                    shirt_color="#3B82F6",
                    pants_color="#1E293B",
                    shoes_color="#0F172A",
                ),
                hair_style=HairStyle.SHORT_PARTED.value,
                eye_style=EyeStyle.ROUND.value,
                clothing_style=ClothingStyle.CASUAL.value,
                voice_id="tr_male_ali",
                default_expression=CharacterExpression.CHEERFUL,
                default_pose=CharacterPose.STANDING,
                proportions=BodyProportions(),
                blend_file_path=os.path.join(base_assets_dir, "characters", "char_ali", "char_ali.blend"),
                thumbnail_path=os.path.join(base_assets_dir, "thumbnails", "char_ali.png"),
                is_builtin=True,
            ),
            Character(
                id="char_ayse",
                name="Ayşe",
                description="Zeki, neşeli ve pratik kadın karakter. Pembe bluz, koyu pantolon ve kahverengi saç.",
                gender="female",
                palette=CharacterColorPalette(
                    skin_tone="#FCE7D0",
                    hair_color="#B45309",
                    eye_color="#1E293B",
                    shirt_color="#EC4899",
                    pants_color="#334155",
                    shoes_color="#0F172A",
                ),
                hair_style=HairStyle.BOB_CUT.value,
                eye_style=EyeStyle.ROUND.value,
                clothing_style=ClothingStyle.CASUAL.value,
                voice_id="tr_female_ayse",
                default_expression=CharacterExpression.CHEERFUL,
                default_pose=CharacterPose.STANDING,
                proportions=BodyProportions(),
                blend_file_path=os.path.join(base_assets_dir, "characters", "char_ayse", "char_ayse.blend"),
                thumbnail_path=os.path.join(base_assets_dir, "thumbnails", "char_ayse.png"),
                is_builtin=True,
            ),
        ]

        for char in builtin_chars:
            if not self.char_repo.get_by_id(char.id):
                if self.blender_gen:
                    try:
                        b_path, t_path = self.blender_gen.generate_character_assets(char)
                        char.set_asset_paths(b_path, t_path)
                    except Exception as e:
                        logger.warning("Could not pre-render character %s: %s", char.id, e)
                self.char_repo.save(char)

        # 2. Built-in Backgrounds
        backgrounds = [
            ("bg_modern_cafe", "Modern Kafe", "Sıcak iç mekan kahve dükkanı, barista tezgahı ve pencereler", ["cafe", "interior", "coffee"]),
            ("bg_office", "Modern Ofis", "Aydınlık ofis çalışma ortamı, çalışma masası ve beyaz tahta", ["office", "work", "business"]),
            ("bg_park", "Şehir Parkı", "Açık hava park, çim alan, yürüyüş yolu ve ahşap bank", ["park", "nature", "outdoor"]),
            ("bg_living_room", "Oturma Odası", "Samimi oturma odası, modern kanepe ve sıcak aydınlatma", ["home", "cozy", "living"]),
            ("bg_tech_studio", "Teknoloji Stüdyosu", "Podcast & YouTube stüdyosu, akustik paneller ve neon aydınlatma", ["studio", "tech", "podcast"]),
        ]

        for aid, aname, adesc, tags in backgrounds:
            if not self.asset_repo.get_by_id(aid):
                asset = StudioAsset(
                    id=aid,
                    name=aname,
                    category=AssetCategory.BACKGROUND,
                    description=adesc,
                    file_path=os.path.join(base_assets_dir, "backgrounds", f"{aid}.blend"),
                    asset_format=AssetFormat.BLEND,
                    thumbnail_path=os.path.join(base_assets_dir, "thumbnails", f"{aid}.png"),
                    version="1.0",
                    tags=tags,
                    is_builtin=True,
                )
                if self.blender_gen:
                    try:
                        b_path, t_path = self.blender_gen.generate_scene_asset(asset)
                        asset.set_file_paths(b_path, t_path)
                    except Exception as e:
                        logger.warning("Could not pre-render background %s: %s", aid, e)
                self.asset_repo.save(asset)

        # 3. Built-in Props
        props = [
            ("prop_table", "Kafe Masası", "Modern ahşap yüzeyli, metal ayaklı yuvarlak kafe masası", ["furniture", "cafe", "table"]),
            ("prop_chair", "Kafe Sandalyesi", "Modern döşemeli şık kafe sandalyesi", ["furniture", "cafe", "seating"]),
            ("prop_coffee_cup", "Kahve Fincanı", "Sıcak kahve dolu porselen fincan ve tabağı", ["drink", "cafe", "cup"]),
            ("prop_coffee_machine", "Espresso Makinesi", "Paslanmaz çelik profesyonel espresso makinesi", ["appliance", "cafe", "coffee"]),
            ("prop_laptop", "Dizüstü Bilgisayar", "Modern alüminyum gövdeli açık dizüstü bilgisayar", ["tech", "office", "computer"]),
            ("prop_smartphone", "Akıllı Telefon", "İnce çerçeveli şık akıllı telefon", ["tech", "mobile", "phone"]),
            ("prop_books", "Kitap Yığını", "Üst üste konulmuş renkli kitaplar", ["education", "prop", "reading"]),
        ]

        for aid, aname, adesc, tags in props:
            if not self.asset_repo.get_by_id(aid):
                asset = StudioAsset(
                    id=aid,
                    name=aname,
                    category=AssetCategory.PROP,
                    description=adesc,
                    file_path=os.path.join(base_assets_dir, "props", f"{aid}.blend"),
                    asset_format=AssetFormat.BLEND,
                    thumbnail_path=os.path.join(base_assets_dir, "thumbnails", f"{aid}.png"),
                    version="1.0",
                    tags=tags,
                    is_builtin=True,
                )
                if self.blender_gen:
                    try:
                        b_path, t_path = self.blender_gen.generate_scene_asset(asset)
                        asset.set_file_paths(b_path, t_path)
                    except Exception as e:
                        logger.warning("Could not pre-render prop %s: %s", aid, e)
                self.asset_repo.save(asset)

        # 4. Built-in Lighting Presets
        lightings = [
            ("light_warm_interior", "Sıcak İç Mekan", "Samimi, sıcak tonlu iç mekan 3-noktalı stüdyo aydınlatması (3200K)", ["lighting", "warm", "interior"]),
            ("light_daylight", "Doğal Gün Işığı", "Açık hava ve parlak gün ışığı simülasyonu (5500K)", ["lighting", "daylight", "bright"]),
            ("light_neon_night", "Neon Gece", "Modern siberpunk tarzı çift renkli (Cyan/Pembe) neon stüdyo ışığı", ["lighting", "neon", "night"]),
        ]

        for aid, aname, adesc, tags in lightings:
            if not self.asset_repo.get_by_id(aid):
                asset = StudioAsset(
                    id=aid,
                    name=aname,
                    category=AssetCategory.LIGHTING,
                    description=adesc,
                    file_path=os.path.join(base_assets_dir, "backgrounds", f"{aid}.blend"),
                    asset_format=AssetFormat.BLEND,
                    thumbnail_path=os.path.join(base_assets_dir, "thumbnails", f"{aid}.png"),
                    version="1.0",
                    tags=tags,
                    is_builtin=True,
                )
                self.asset_repo.save(asset)
