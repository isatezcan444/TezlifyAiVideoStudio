# Tezlify YouTube Creator Studio

> **Yerel öncelikli (local-first), Clean Architecture tabanlı YouTube kanal yönetimi ve yayın stüdyosu**

Tezlify Creator Studio; macOS üzerinde çalışan, YouTube kanalınızı bağlayıp videolarınızı yönetmenizi, zamanlamanızı ve analitiklerinizi takip etmenizi sağlayan bağımsız bir masaüstü web uygulamasıdır. 2.0 sürümüyle birlikte video üretimi (sahne grafiği, karakter/rig, animasyon, seslendirme, render hattı) üründen tamamen çıkarılmış; odak YouTube içerik yönetimine taşınmıştır.

---

## 📺 Mevcut Yetenekler

- **YouTube OAuth 2.0 PKCE:** RFC 7636 uyumlu S256 PKCE ve yerel loopback yönlendirmesiyle güvenli Google yetkilendirmesi. Mevcut bağlantılar korunur; token yalnızca süresi dolduğunda yenilenir.
- **macOS Keychain Token Güvenliği:** Erişim ve yenileme anahtarları veritabanında düz metin tutulmaz; macOS Keychain içinde saklanır.
- **Resumable Upload:** Videolar 4 MB bloklar halinde yüklenir; kesintide Google'ın HTTP 308 yanıtı üzerinden kaldığı byte'tan devam eder.
- **Kanal Yönetimi:** Kanal profili, video listesi ve detayları, başlık/açıklama/etiket/kategori/gizlilik düzenleme, oynatma listeleri.
- **Zamanlama ve Yayın Kayıtları:** İleri tarihli yayın planı, arka plan zamanlayıcı, retry/recovery ve yerel yayın geçmişi.
- **Gerçek Dashboard:** Abone, görüntüleme ve video sayıları YouTube Data API'den; günlük analitik YouTube Analytics API'den; planlama ve yayın geçmişi yerel SQLite'tan. Kaynak kullanılamadığında değer uydurulmaz.
- **Analytics:** 7/28/90/365 gün ve özel aralık; görüntüleme, izlenme süresi, ortalama süre/yüzde, abone kazanım/kaybı, trafik kaynağı, ülke, cihaz, video kırılımı. Gelir yalnızca parasal analitik izni varsa raporlanır.
- **Yorumlar:** Kanal/video yorumlarını listeleme, yanıtlama ve moderasyon (API'nin izin verdiği ölçüde).
- **Yerel Medya Kütüphanesi:** Chunked import, SHA-256 duplicate kontrolü, FFprobe/fallback metadata, HTTP Range streaming ve thumbnail. FFmpeg yalnızca mevcut medyanın analizi ve oynatımı için kullanılır.
- **Platform Katmanı:** `platforms`, `channels`, `videos`, `publishing`, `scheduling`, `analytics`, `comments`, `media_library` alanları platformdan bağımsız portlarla tanımlıdır; bu sürümde yalnızca YouTube uygulanmıştır.
- **Vuexy Tasarım Sistemi:** #7367F0 paleti, koyu/açık tema, duyarlı kartlar ve tutarlı bileşenler.

---

## 🛠 Sistem Gereksinimleri ve Kurulum

### 1. Ön Koşullar
- **İşletim Sistemi:** macOS (Apple Silicon veya Intel) ya da Linux/Windows
- **Python:** 3.10 veya üzeri
- **Node.js:** 20.x veya üzeri
- **npm:** 10.x veya üzeri
- **FFmpeg (isteğe bağlı):** Video metadata analizi ve thumbnail üretimi için. Blender veya başka bir 3D aracı gerekmez.

```bash
brew install ffmpeg   # isteğe bağlı
```

---

### 2. Kurulum Adımları

```bash
cd /Users/isatezcan/Documents/Github/Tezlify-AI-Video-Studio

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e backend

cd frontend
npm install
cd ..

cp .env.example .env
```

`.env` içine Google Cloud Console > OAuth 2.0 Client ID bilgilerinizi girin:

```bash
GOOGLE_CLIENT_ID="..."
GOOGLE_CLIENT_SECRET="..."
```

Google Cloud projesinde **YouTube Data API v3** ve **YouTube Analytics API** etkin olmalıdır. Kanal bağlantısı Ayarlar > Bağlı Hesaplar ekranından yapılır.

---

## 🏁 Uygulamayı Başlatma

```bash
python scripts/start.py
```

Bu komut SQLite şemasını hazırlar, FastAPI backend'i `http://127.0.0.1:8000`, Vite + React frontend'i `http://127.0.0.1:5173` üzerinde başlatır ve tarayıcıyı açar. Durdurmak için `Ctrl + C`.

---

## 🩺 Sistem Teşhisi ve Testler

```bash
# Çevre ve bağımlılık denetimi
python scripts/doctor.py

# Backend birim + entegrasyon testleri
.venv/bin/python -m pytest backend/tests -q

# Frontend testleri ve üretim derlemesi
cd frontend && npx vitest run && npm run build
```

Testler izole bir `DATA_DIR` kullanır; gerçek kullanıcı verisine dokunmaz. YouTube çağrıları mock/sandbox transport ile doğrulanır.

---

## 📁 Mimari Dizin Yapısı

```
Tezlify-AI-Video-Studio/
├── backend/
│   ├── src/tezlify_studio/
│   │   ├── domain/               # Entities, Value Objects, Enums, Exceptions
│   │   ├── application/          # Use Cases, DTOs, Ports (channel/analytics/comment/platform)
│   │   ├── infrastructure/       # SQLite, SQLAlchemy, Storage, FFmpeg probe, YouTube adapter
│   │   └── presentation/         # FastAPI routes, schemas, DI container
│   ├── tests/                    # Unit ve integration testleri
│   └── alembic/                  # Şema versiyonlama
├── frontend/
│   ├── src/
│   │   ├── components/           # ui, Layout, video, youtube, schedule
│   │   ├── pages/                # Dashboard, ChannelOverview, Videos, Analytics, Comments...
│   │   ├── services/             # Typed API client
│   │   └── types/                # creator.ts, media.ts
├── scripts/                      # start, doctor, verify_e2e, sample video
└── data/                         # Yerel depo (git dışı)
    ├── database/
    ├── media/
    └── temp/
```

---

## 🗺️ Sürüm Durumu

- [x] **Aşama 1:** Local Studio Core & manuel video içe aktarma
- [x] **Aşama 2:** YouTube Publisher (OAuth PKCE, Keychain, resumable upload)
- [x] **Aşama 3:** Zamanlama, yayın kayıtları ve retry/recovery
- [x] **Aşama 4:** YouTube Creator Studio pivotu (dashboard, analytics, comments, kanal yönetimi)
- [x] **Aşama 5.0 – 5.5:** Video üretim/animasyon hattının kaldırılması ve ürün sadeleştirmesi
- [ ] **Sonraki:** Instagram/TikTok adaptörleri, gelir merkezi (yalnızca API izinleriyle)
