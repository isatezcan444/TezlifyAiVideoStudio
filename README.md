# Tezlify AI Video Studio

> **Local-First, Clean Architecture tabanlı Profesyonel Video Üretim ve Yayın Stüdyosu**

Tezlify AI Video Studio; Python merkezli, yerel bilgisayarda çalışan, gelecekte Blender 2.5D ve yapay zekâ destekli modüler animasyon üretimini sosyal medya yayıncılığıyla birleştirecek bağımsız bir stüdyo yazılımıdır.

---

## 🚀 Aşama 1: Local Studio Core (Mevcut Yetenekler)

- **Temiz Mimari (Clean Architecture):** Domain, Application, Infrastructure ve Presentation katmanları birbirinden tamamen izoledir.
- **Güvenli Manuel Video İçe Aktarma:** Büyük dosyalar belleğe alınmadan chunked stream ile diske yazılır.
- **SHA-256 İçerik Özeti & Duplicate Kontrolü:** Aynı dosyanın kütüphaneye tekrar tekrar yüklenmesi anında engellenir.
- **Video Analizi & Fallback Desteği:** FFprobe mevcutsa donanım hızlandırmalı analiz yapar; FFprobe kurulu değilse saf Python ISO BMFF başlık ayrıştırıcısıyla (duration, width, height, aspect ratio) kesintisiz çalışmaya devam eder.
- **HTML5 Seekable Streaming (HTTP Range):** Video oynatıcıda ileri ve geri sarma işlemleri HTTP 206 Partial Content akışı ile desteklenir.
- **Tezlify Tasarım Sistemi:** Vuexy renk paleti, koyu/açık tema (Dark/Light), duyarlı kartlar, istatistikler ve modal yapısı.
- **Tek Komutla Başlatma:** `python scripts/start.py` ile FastAPI backend ve Vite frontend tek komutla ayağa kaldırılır.

---

## 🛠 Sistem Gereksinimleri ve Kurulum

### 1. Ön Koşullar
- **İşletim Sistemi:** macOS (Apple Silicon M serisi veya Intel) ya da Linux/Windows
- **Python:** 3.10 veya üzeri
- **Node.js:** 20.x veya üzeri
- **npm:** 10.x veya üzeri

*(İsteğe Bağlı) FFmpeg ve Blender Kurulumu:*
```bash
# Video analizinde tam performans ve thumbnail üretimi için:
brew install ffmpeg

# Gelecekteki 2.5D animasyon sahneleri için:
brew install --cask blender
```

---

### 2. Kurulum Adımları

```bash
# 1. Proje dizinine girin
cd /Users/isatezcan/Documents/Github/Tezlify-AI-Video-Studio

# 2. Python sanal ortamı oluşturun ve bağımlılıkları yükleyin
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e backend

# 3. Frontend bağımlılıklarını kurun
cd frontend
npm install
cd ..

# 4. Ortam dosyasını hazırlayın
cp .env.example .env
```

---

## 🏁 Uygulamayı Başlatma

Uygulamayı hem backend hem frontend olarak tek bir komutla başlatmak için:

```bash
python scripts/start.py
```

Bu komut:
1. SQLite veritabanı şemasını hazırlar,
2. FastAPI backend sunucusunu `http://127.0.0.1:8000` portunda başlatır,
3. Vite + React frontend sunucusunu `http://127.0.0.1:5173` portunda çalıştırır,
4. Sağlık kontrollerini tamamladıktan sonra tarayıcınızda uygulamayı açar.
5. Durdurmak için terminalde `Ctrl + C` tuşlamanız yeterlidir; tüm arka plan süreçleri temiz bir şekilde sonlandırılır.

---

## 🩺 Sistem Teşhisi ve Testler

### Sistem Denetimi (Doctor Script)
Donanım, işletim sistemi, Python, Node, FFmpeg ve Blender durumunu tek bakışta görmek için:
```bash
python scripts/doctor.py
```

### Otomatik Testleri Çalıştırma
```bash
# Backend pytest birim ve entegrasyon testleri (10 test):
.venv/bin/pytest backend/tests -v

# Uçtan uca video yükleme, streaming, duplicate ve silme testi:
.venv/bin/python scripts/verify_e2e.py

# Frontend derleme (build) testi:
cd frontend && npm run build
```

---

## 📁 Mimari Dizin Yapısı

```
Tezlify-AI-Video-Studio/
├── backend/
│   ├── src/tezlify_studio/
│   │   ├── domain/               # Saf Python: Entities, Value Objects, Enums, Exceptions
│   │   ├── application/          # Use Cases, DTOs, Ports/Interfaces
│   │   ├── infrastructure/       # SQLite, SQLAlchemy ORM, Storage, FFmpeg/Probe, Config
│   │   └── presentation/         # FastAPI, Schemas, Dependency Injection Container
│   ├── tests/                    # Unit ve Integration testleri
│   └── alembic/                  # Veritabanı şema versiyonlama
├── frontend/
│   ├── src/
│   │   ├── components/ui/        # Tezlify tasarım bileşenleri (Button, Card, Badge, Modal, vb.)
│   │   ├── components/Layout/    # Sidebar, TopHeader
│   │   ├── components/video/     # VideoDetailsModal, HTML5 Range Player
│   │   ├── pages/                # Dashboard, VideoLibrary, ImportVideo, Settings
│   │   ├── services/             # Typed API Client
│   │   └── hooks/                # useTheme (Dark/Light modu)
├── scripts/
│   ├── start.py                  # Tek komutla backend + frontend başlatıcı
│   ├── doctor.py                 # Çevre ve bağımlılık analiz aracı
│   ├── verify_e2e.py             # Uçtan uca otomatik doğrulama testi
│   └── generate_sample_video.py  # Test için gerçek MP4 üretici
└── data/                         # Local storage (Git tarafından yok sayılır)
    ├── database/                 # SQLite veritabanı dosyası
    ├── media/                    # Kalıcı video deposu
    └── temp/                     # Geçici yükleme dizini
```

---

## 🗺️ Yol Haritası

- [x] **Aşama 0:** Altyapı, çevre ve Tezlify UI analizleri
- [x] **Aşama 1:** Local Studio Core & Manuel Video İçe Aktarma
- [ ] **Aşama 2:** YouTube Publisher (OAuth & Doğrudan Yükleme)
- [ ] **Aşama 3:** Scheduler ve İçerik Takvimi
- [ ] **Aşama 4:** LLM Provider Center (GLM, OpenAI, Ollama)
- [ ] **Aşama 5:** Story Director & Pydantic Scene JSON Doğrulayıcı
- [ ] **Aşama 6:** Asset, Puppet ve Rig Kütüphanesi
- [ ] **Aşama 7:** Blender 2.5D Scene Builder (Subprocess)
- [ ] **Aşama 8:** Render Worker (Per-Scene Chunking) & FFmpeg Montaj
- [ ] **Aşama 9:** Ses, TTS ve Lip-Sync
- [ ] **Aşama 10:** Instagram, TikTok ve Gelir Merkezi
