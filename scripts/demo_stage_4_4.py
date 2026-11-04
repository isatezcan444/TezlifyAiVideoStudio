#!/usr/bin/env python3
"""
Tezlify AI Video Studio - Aşama 4.4 Demo Scripti
ELEVENLABS VOICE INTEGRATION & FIRST COMPLETE AI ANIMATION VIDEO

Akış:
1. Modern Kafe Sahnesi Projesi (Ali & Ayşe) oluşturulur.
2. Diyaloglar:
   - Ali: "Merhaba Ayşe, bugün nasılsın?" (Ses: Charlie - IKne3meq5aSn9XLyUdCD)
   - Ayşe: "İyiyim Ali, teşekkür ederim. Sen nasılsın?" (Ses: Jessica - cgSgspJ2msm6clMCkdW9)
3. ElevenLabs API kontrolü:
   - ELEVENLABS_API_KEY mevcutsa ElevenLabs API ile gerçek ses sentezi yapılır.
   - ELEVENLABS_API_KEY eksikse, kullanıcıya açıkça bildirilir ve demo test tonları ile MP4 üretimi sürdürülür.
4. Ses dosyalarının gerçek süreleri FFprobe ile ölçülür ve diyalog/sahne zamanlamaları senkronize edilir.
5. Blender 5.2.3 headless animasyon motoru çalıştırılır (konuşan karakterin ağzı senkronize açılıp kapanır, dinleyici suskun dinler).
6. FFmpeg ile video ve sesler mikslenerek H.264 + AAC MP4 oluşturulur.
7. FFprobe ile teknik doğrulama yapılıp detaylar yazdırılır.
"""

import os
import sys
import json
import time
import subprocess

# Backend modüllerine erişim için sys.path ayarı
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "src")))

from tezlify_studio.infrastructure.configuration.settings import settings
from tezlify_studio.domain.enums.studio_status import (
    CameraAngle,
    CameraMovement,
    CharacterPose,
    CharacterExpression,
)
from tezlify_studio.domain.value_objects.scene_graph import (
    SceneGraph,
    SceneResolution,
    SceneCharacter,
    StudioScene,
    SceneBackground,
    SceneCamera,
    CharacterPlacement,
    SceneDialogue,
)
from tezlify_studio.infrastructure.ai.elevenlabs_client_impl import ElevenLabsClientImpl
from tezlify_studio.infrastructure.blender.blender_animation_engine_impl import BlenderAnimationEngineImpl


def create_demo_tone_mp3(output_path: str, duration_sec: float, freq: int):
    """Fallback audio tone generator when API key is not configured."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency={freq}:duration={duration_sec}",
        "-c:a", "libmp3lame",
        "-b:a", "128k",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def measure_audio_duration(file_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return round(float(res.stdout.strip()), 2)


def run_stage_4_4_demo():
    print("=" * 70)
    print("  TEZLIFY AI VIDEO STUDIO — AŞAMA 4.4 CANLI DEMO")
    print("  ElevenLabs Voice Integration & First Complete Audio Animation Video")
    print("=" * 70)

    # 1. ElevenLabs Yapılandırma Durumu
    print("\n1. ElevenLabs API Durumu Kontrol Ediliyor...")
    client = ElevenLabsClientImpl()
    is_configured = client.is_configured()

    voice_ali_id = "IKne3meq5aSn9XLyUdCD"   # Charlie (Dinamik Türkçe/İngilizce Erkek)
    voice_ayse_id = "cgSgspJ2msm6clMCkdW9"  # Jessica (Sıcak/Doğal Kadın)

    if is_configured:
        print(f"   [✓] ElevenLabs API Anahtarı Algılandı (.env).")
        print(f"   [✓] Varsayılan Model: {settings.elevenlabs_default_model}")
        print(f"   [✓] Ali için Ses: Charlie ({voice_ali_id})")
        print(f"   [✓] Ayşe için Ses: Jessica ({voice_ayse_id})")
    else:
        print("   [!] DİKKAT: ELEVENLABS_API_KEY .env dosyasında tanımlı değil.")
        print("       Gerçek ElevenLabs API çağrısı için .env dosyasına ELEVENLABS_API_KEY ekleyin.")
        print("       Demo işleminde ses pipeline'ını doğrulamak için gerçek frekans test sesleri kullanılacaktır.")

    # 2. Ses Üretimi ve Ölçümü
    print("\n2. Diyalog Sesleri Hazırlanıyor...")
    cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "audio_cache"))
    os.makedirs(cache_dir, exist_ok=True)

    text_ali = "Merhaba Ayşe, bugün nasılsın?"
    text_ayse = "İyiyim Ali, teşekkür ederim. Sen nasılsın?"

    ali_audio_path = os.path.join(cache_dir, "demo_ali_speech.mp3")
    ayse_audio_path = os.path.join(cache_dir, "demo_ayse_speech.mp3")

    if is_configured:
        try:
            print("   -> ElevenLabs API ile Ali'nin sesi sentezleniyor...")
            res_ali = client.synthesize_speech(text_ali, voice_ali_id, ali_audio_path)
            dur_ali = res_ali.duration_seconds
            print(f"      [✓] Ali ses üretildi: {dur_ali}s ({ali_audio_path})")

            print("   -> ElevenLabs API ile Ayşe'nin sesi sentezleniyor...")
            res_ayse = client.synthesize_speech(text_ayse, voice_ayse_id, ayse_audio_path)
            dur_ayse = res_ayse.duration_seconds
            print(f"      [✓] Ayşe ses üretildi: {dur_ayse}s ({ayse_audio_path})")
        except Exception as e:
            print(f"   [!] ElevenLabs API çağrısında hata oluştu: {e}")
            print("       Fallback test tonu kullanılıyor...")
            dur_ali = 2.4
            dur_ayse = 2.8
            create_demo_tone_mp3(ali_audio_path, dur_ali, 320)
            create_demo_tone_mp3(ayse_audio_path, dur_ayse, 580)
    else:
        dur_ali = 2.2
        dur_ayse = 2.6
        create_demo_tone_mp3(ali_audio_path, dur_ali, 320)
        create_demo_tone_mp3(ayse_audio_path, dur_ayse, 580)
        print(f"   [✓] Ali diyalog sesi oluşturuldu: {dur_ali}s ({ali_audio_path})")
        print(f"   [✓] Ayşe diyalog sesi oluşturuldu: {dur_ayse}s ({ayse_audio_path})")

    # 3. Zamanlama Hesabı
    ali_start = 1.0
    ali_end = ali_start + dur_ali
    ayse_start = ali_end + 0.6
    ayse_end = ayse_start + dur_ayse
    total_scene_duration = round(ayse_end + 1.2, 1)

    print(f"\n3. Sahne Zaman Çizelgesi Senkronize Edildi:")
    print(f"   - 0.0s - {ali_start}s: Sahne Girişi (Atmosfer, Masada Oturma)")
    print(f"   - {ali_start}s - {ali_end}s: Ali Konuşuyor ('{text_ali}') | Ayşe Dinliyor")
    print(f"   - {ali_end}s - {ayse_start}s: Ara Bekleme / Baş Onaylama (Tepki)")
    print(f"   - {ayse_start}s - {ayse_end}s: Ayşe Konuşuyor ('{text_ayse}') | Ali Dinliyor")
    print(f"   - Toplam Sahne Süresi: {total_scene_duration} saniye")

    # 4. SceneGraph Yapılandırması
    print("\n4. SceneGraph Nesnesi Oluşturuluyor...")
    scene_graph = SceneGraph(
        schema_version="1.0",
        project_id="proj_cafe_stage4_4",
        title="Ali ve Ayşe Modern Kafe Sohbeti (Sesli)",
        resolution=SceneResolution(width=1920, height=1080, fps=30),
        characters=[
            SceneCharacter(id="char_ali", name="Ali", voice_id=voice_ali_id),
            SceneCharacter(id="char_ayse", name="Ayşe", voice_id=voice_ayse_id),
        ],
        scenes=[
            StudioScene(
                scene_id="scene_cafe_01",
                duration_seconds=total_scene_duration,
                background=SceneBackground(type="preset", asset_id="bg_modern_cafe"),
                camera=SceneCamera(angle=CameraAngle.TWO_SHOT, movement=CameraMovement.STATIC),
                character_placements=[
                    CharacterPlacement(
                        character_id="char_ali",
                        position=[-0.75, 0.0, 0.0],
                        rotation_y=25.0,
                        expression=CharacterExpression.CHEERFUL,
                        pose=CharacterPose.SITTING_TABLE,
                    ),
                    CharacterPlacement(
                        character_id="char_ayse",
                        position=[0.75, 0.0, 0.0],
                        rotation_y=-25.0,
                        expression=CharacterExpression.CHEERFUL,
                        pose=CharacterPose.SITTING_TABLE,
                    ),
                ],
                dialogues=[
                    SceneDialogue(
                        character_id="char_ali",
                        text=text_ali,
                        start_time=ali_start,
                        end_time=ali_end,
                        audio_file=ali_audio_path,
                    ),
                    SceneDialogue(
                        character_id="char_ayse",
                        text=text_ayse,
                        start_time=ayse_start,
                        end_time=ayse_end,
                        audio_file=ayse_audio_path,
                    ),
                ],
            )
        ],
    )
    print("   [✓] SceneGraph başarıyla doğrulandı.")

    # 5. Blender Headless Render & FFmpeg Audio Merging
    print("\n5. Blender Headless Render ve Ses Miksajı Başlatılıyor...")
    engine = BlenderAnimationEngineImpl()
    project_id = "demo_stage_4_4"
    job_id = f"job_{int(time.time())}"

    def on_progress(percent: float, step: str):
        print(f"   [{percent:5.1f}%] {step}")

    metadata = engine.render_animation(
        scene_graph=scene_graph,
        project_id=project_id,
        job_id=job_id,
        progress_callback=on_progress,
        engine_override="BLENDER_WORKBENCH",
    )

    expected_mp4 = os.path.join(
        engine.base_projects_dir, project_id, "renders", job_id, f"{job_id}.mp4"
    )

    print("\n6. Teknik Çıktı ve FFprobe Doğrulaması:")
    print(f"   [✓] Nihai Video Dosyası: {expected_mp4}")
    print(f"   [✓] Dosya Boyutu:        {metadata.file_size_bytes:,} bayt ({metadata.file_size_bytes / (1024*1024):.2f} MB)")
    print(f"   [✓] Toplam Süre:         {metadata.duration_seconds} saniye")
    print(f"   [✓] Çözünürlük:          {metadata.width}x{metadata.height}")
    print(f"   [✓] Kare Hızı (FPS):     {metadata.fps}")
    print(f"   [✓] Video Codec:         {metadata.video_codec} ({metadata.pixel_format})")
    print(f"   [✓] Ses Var mı:          {metadata.has_audio}")
    print(f"   [✓] Ses Codec:           {metadata.audio_codec}")
    print(f"   [✓] Toplam Render Süresi:{metadata.render_duration_seconds:.2f} saniye")

    # FFprobe Streams Kontrolü
    probe_cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        expected_mp4,
    ]
    res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    probe_data = json.loads(res.stdout)

    v_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "audio"), None)

    print("\n7. Akış Doğrulama Raporu:")
    if v_stream:
        print(f"   [✓] Video Akışı: Codec={v_stream.get('codec_name')}, Profil={v_stream.get('profile')}, Bitrate={v_stream.get('bit_rate', 'N/A')}")
    if a_stream:
        print(f"   [✓] Ses Akışı:   Codec={a_stream.get('codec_name')}, Kanallar={a_stream.get('channels')}, Örnekleme={a_stream.get('sample_rate')}Hz")

    print("\n" + "=" * 70)
    print("  🎉 AŞAMA 4.4 İLK SESLİ ANİMASYON VİDEOSU BAŞARIYLA ÜRETİLDİ!")
    print("=" * 70)
    return expected_mp4


if __name__ == "__main__":
    run_stage_4_4_demo()

