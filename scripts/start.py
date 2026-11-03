#!/usr/bin/env python3
import os
import sys
import time
import signal
import subprocess
import urllib.request
import webbrowser

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

BACKEND_URL = "http://127.0.0.1:8000"
HEALTH_URL = f"{BACKEND_URL}/api/v1/health"
FRONTEND_URL = "http://127.0.0.1:5173"

processes = []

def get_python_bin() -> str:
    venv_py = os.path.join(PROJECT_ROOT, ".venv", "bin", "python3")
    if os.path.exists(venv_py):
        return venv_py
    return sys.executable

def cleanup(sig=None, frame=None):
    print("\n🛑 Tezlify AI Video Studio kapatılıyor...")
    for p in processes:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
    print("👋 Tüm servisler güvenli bir şekilde sonlandırıldı.")
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def wait_for_url(url: str, timeout_seconds: int = 15) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TezlifyHealthCheck"})
            with urllib.request.urlopen(req, timeout=1.5) as response:
                if response.status in (200, 304):
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    print("=" * 65)
    print("     TEZLIFY AI VIDEO STUDIO - LOCAL RUNTIME BAŞLATILIYOR")
    print("=" * 65)

    py_bin = get_python_bin()

    # 1. Database initialization & Alembic check
    print("\n📦 1. Veritabanı ve migrasyonlar kontrol ediliyor...")
    init_cmd = [
        py_bin, "-c",
        "from tezlify_studio.infrastructure.persistence.database import init_db; init_db()"
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(BACKEND_DIR, "src")
    res = subprocess.run(init_cmd, cwd=PROJECT_ROOT, env=env)
    if res.returncode != 0:
        print("❌ Veritabanı başlatılamadı.")
        sys.exit(1)
    print("   [✓] Veritabanı tabloları hazır.")

    # 2. Start Backend
    print(f"\n🚀 2. FastAPI Backend başlatılıyor ({BACKEND_URL})...")
    backend_proc = subprocess.Popen(
        [
            py_bin, "-m", "uvicorn",
            "tezlify_studio.presentation.api.app:app",
            "--host", "127.0.0.1",
            "--port", "8000"
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    processes.append(backend_proc)

    if not wait_for_url(HEALTH_URL, timeout_seconds=12):
        print("❌ Backend sağlık kontrolüne yanıt vermedi.")
        cleanup()

    print("   [✓] Backend başarıyla bağlandı ve yanıt veriyor.")

    # 3. Start Frontend
    print(f"\n🎨 3. Vite + React Frontend başlatılıyor ({FRONTEND_URL})...")
    npm_bin = "npm"
    frontend_proc = subprocess.Popen(
        [npm_bin, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"],
        cwd=FRONTEND_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    processes.append(frontend_proc)

    if not wait_for_url(FRONTEND_URL, timeout_seconds=15):
        print("❌ Frontend sunucusuna bağlanılamadı.")
        cleanup()

    print("   [✓] Frontend arayüzü hazır.")

    # 4. Open in browser
    print("\n🌐 4. Tarayıcıda açılıyor: http://localhost:5173")
    try:
        webbrowser.open("http://localhost:5173")
    except Exception:
        pass

    print("\n" + "=" * 65)
    print("  ✨ Tezlify AI Video Studio aktif ve çalışıyor!")
    print("  Uygulamayı durdurmak için konsolda Ctrl+C tuşlayın.")
    print("=" * 65 + "\n")

    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
