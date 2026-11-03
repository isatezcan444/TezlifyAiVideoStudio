#!/usr/bin/env python3
import sys
import os
import shutil
import platform
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def check_mark(status: bool) -> str:
    return "\033[92m[✓ OK]\033[0m" if status else "\033[93m[! UYARI]\033[0m"

def error_mark() -> str:
    return "\033[91m[✗ HATA]\033[0m"

def main():
    print("=" * 60)
    print("  TEZLIFY AI VIDEO STUDIO - SISTEM VE ORTAM DENETIMI")
    print("=" * 60)

    # 1. OS & Machine
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    print(f"\n1. Isletim Sistemi: {os_info}")

    # 2. Python
    py_ver = sys.version.split()[0]
    py_ok = sys.version_info >= (3, 10)
    print(f"2. Python Surumu: {py_ver} {check_mark(py_ok)}")

    # 3. Node & NPM
    node_bin = shutil.which("node")
    npm_bin = shutil.which("npm")
    node_ver = "Bulunamadi"
    npm_ver = "Bulunamadi"
    if node_bin:
        res = subprocess.run([node_bin, "-v"], capture_output=True, text=True)
        node_ver = res.stdout.strip()
    if npm_bin:
        res = subprocess.run([npm_bin, "-v"], capture_output=True, text=True)
        npm_ver = res.stdout.strip()

    print(f"3. Node.js: {node_ver} {check_mark(bool(node_bin))}")
    print(f"   npm:     {npm_ver} {check_mark(bool(npm_bin))}")

    # 4. Media Tools: FFmpeg & FFprobe
    ffmpeg_bin = (
        shutil.which("ffmpeg")
        or ("/opt/homebrew/bin/ffmpeg" if os.path.exists("/opt/homebrew/bin/ffmpeg") else None)
        or ("/usr/local/bin/ffmpeg" if os.path.exists("/usr/local/bin/ffmpeg") else None)
    )
    ffprobe_bin = (
        shutil.which("ffprobe")
        or ("/opt/homebrew/bin/ffprobe" if os.path.exists("/opt/homebrew/bin/ffprobe") else None)
        or ("/usr/local/bin/ffprobe" if os.path.exists("/usr/local/bin/ffprobe") else None)
    )
    print(f"4. FFmpeg:  {ffmpeg_bin or 'Sistemde yok (Python fallback devrede)'} {check_mark(bool(ffmpeg_bin))}")
    print(f"   FFprobe: {ffprobe_bin or 'Sistemde yok (Python fallback devrede)'} {check_mark(bool(ffprobe_bin))}")
    if not ffmpeg_bin:
        print("   \033[90m-> Kurulum onerisi: brew install ffmpeg\033[0m")

    # 5. Blender
    blender_bin = shutil.which("blender")
    blender_app = os.path.exists("/Applications/Blender.app")
    blender_status = bool(blender_bin or blender_app)
    print(f"5. Blender: {'Mevcut' if blender_status else 'Kurulu degil (Asama 6 icin planlandi)'} {check_mark(blender_status)}")
    if not blender_status:
        print("   \033[90m-> Asama 6-8 oncesi kurulum onerisi: brew install --cask blender\033[0m")

    # 6. Database and Storage directories
    data_dir = os.path.join(PROJECT_ROOT, "data")
    db_file = os.path.join(data_dir, "database", "tezlify_studio.db")
    media_dir = os.path.join(data_dir, "media")

    dirs_ok = os.path.exists(media_dir)
    db_ok = os.path.exists(db_file)
    print(f"6. Medya Dizini: {media_dir} {check_mark(dirs_ok)}")
    print(f"   SQLite DB:    {db_file} {check_mark(db_ok)}")

    print("\n" + "=" * 60)
    print("  DENETIM TAMAMLANDI: Asama 1 (Local Studio Core) calismaya hazir.")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()

