# YouTube Publisher Mimari Dokümantasyonu

## 1. Genel Bakış
Tezlify AI Video Studio Aşama 2 (YouTube Publisher), yerel stüdyoda üretilen veya içe aktarılan videoları doğrudan kullanıcının YouTube kanalına aktaran güvenli, dayanıklı ve Clean Architecture prensiplerine tam uyumlu bir yayınlama motorudur.

```mermaid
flowchart TD
    Client["React Frontend (Vuexy / Tailwind)"] -->|"POST /social/youtube/publish"| API["FastAPI Presentation Layer"]
    API -->|"StartPublishRequestDTO"| UC["PublishVideoToYouTubeUseCase (Application)"]
    UC -->|"Get/Save"| PR["PublishRecordRepositoryPort (Domain Port)"]
    UC -->|"Get Account"| SA["SocialAccountRepositoryPort (Domain Port)"]
    UC -->|"Get/Store Token"| TS["TokenStoragePort (Keychain)"]
    UC -->|"Upload Chunk (308 Resume)"| YT["YouTubePublisherPort (HTTP Client)"]
    
    PR -->|"SQLAlchemy ORM"| SQLite[("SQLite WAL Database")]
    TS -->|"/usr/bin/security"| Keychain[("macOS Keychain")]
    YT -->|"HTTP Resumable Protocol"| GoogleYT["Google YouTube Data API v3"]
    
    API -.->|"RFC 8252 Loopback"| DL["DesktopOAuthListener (127.0.0.1:dynamic)"]
```

---

## 2. Clean Architecture Katman Dağılımı

### Domain Katmanı (Saf Python - Harici Çerçeve Bağımlılığı Sıfır)
- **Entities**:
  - `SocialAccount`: Platform, hesap adı, kanal ID, avatar, aktiflik durumu ve token geçerlilik süresi.
  - `PublishRecord`: Video yayınlama oturumu, başlık, açıklama, etiketler, kategori, gizlilik, yükleme ilerlemesi, durum makinesi.
- **Enums**:
  - `SocialPlatform`: `YOUTUBE`
  - `PrivacyStatus`: `PUBLIC`, `UNLISTED`, `PRIVATE`
  - `PublishStatus`: `PENDING`, `AUTHENTICATING`, `UPLOADING`, `PAUSED`, `PROCESSING`, `PUBLISHED`, `FAILED`, `CANCELLED`, `REQUIRES_REAUTH`
- **Exceptions**:
  - `PublishDomainException`, `SocialAccountNotFoundException`, `InvalidPublishStateTransitionException`, `DuplicatePublishException`, `QuotaExceededException`, `TokenStorageException`, `AuthenticationRequiredException`, `UploadSessionExpiredException`

### Application Katmanı (Use Cases & Ports)
- **Ports**:
  - `YouTubePublisherPort`: OAuth URL oluşturma, token takası, profil çekme, chunk yükleme, durum sorgulama.
  - `SocialAccountRepositoryPort`: Sosyal medya hesabı kalıcılık arayüzü.
  - `PublishRecordRepositoryPort`: Yayın kayıtları kalıcılık arayüzü (`get_in_flight_records` desteği ile).
  - `TokenStoragePort`: Güvenli token saklama arayüzü.
- **Use Cases**:
  - `GenerateYouTubeAuthUrlUseCase`: RFC 7636 PKCE S256 anahtar çifti ve dinamik loopback redirect URI oturumu üretir.
  - `CompleteYouTubeAuthenticationUseCase`: Kodu PKCE verifier ile takas edip Keychain'e kaydeder; gerekirse mevcut refresh token'ı korur.
  - `GetConnectedYouTubeAccountUseCase`: Aktif hesabı ve token geçerliliğini denetler.
  - `DisconnectYouTubeAccountUseCase`: Hesabı siler ve Keychain'deki tokenları imha eder.
  - `PublishVideoToYouTubeUseCase`: Google Resumable Upload oturumunu başlatır, 4MB chunklar halinde yükler, ilerlemeyi veritabanına yazar.
  - `ResumeYouTubeUploadUseCase`: Kesintiye uğramış yüklemeyi Google sunucusundaki son byte'tan devam ettirir; 404 oturum süresi dolumlarını ele alır.
  - `CancelYouTubeUploadUseCase`: Devam eden yüklemeyi kullanıcı talebiyle güvenle durdurur.
  - `ReconcilePublishRecordsUseCase`: Uygulama başlarken askıda kalan zombi işleri PAUSED durumuna geçirir.

### Infrastructure Katmanı (Adapters)
- `YouTubeApiClientImpl`: `httpx` tabanlı Google YouTube API v3 istemcisi (Retry-After, üstel geri çekilme ve granüler kota ayrıştırması içerir).
- `KeychainTokenStorageAdapter`: macOS `/usr/bin/security` komut satırı aracı ile işletim sistemi Keychain entegrasyonu (üretimde katı kalıcılık, sıfır hafıza düşüşü).
- `DesktopOAuthListener`: RFC 8252 standartlarında `127.0.0.1` üzerinde dinamik portlu tek kullanımlık HTTP dinleyicisi.
- `SocialAccountRepositoryImpl` & `PublishRecordRepositoryImpl`: SQLite + SQLAlchemy ORM adaptörleri.

### Presentation Katmanı
- FastAPI router: `/api/v1/social/youtube/*`
- React / TypeScript bileşenleri:
  - `YouTubeConnectionCard`: Yetkilendirme durumu, kanal kartı, pop-up tetikleyici.
  - `YouTubePublishModal`: Video seçim, başlık, açıklama, kategori ve gizlilik formu.
  - `PublishProgressCard`: Canlı yükleme yüzdesi, aktarılan byte miktarı, duraklatma ve iptal.
  - `PublishHistoryTable`: Geçmiş yayınlar ve YouTube izleme linkleri.

---

## 3. Durum Makinesi (Publish State Transitions)
Yayın kayıtları yalnızca izin verilen durumlara geçiş yapabilir:
- `PENDING` -> `AUTHENTICATING`, `UPLOADING`, `PAUSED`, `CANCELLED`, `FAILED`
- `AUTHENTICATING` -> `UPLOADING`, `REQUIRES_REAUTH`, `PAUSED`, `FAILED`, `CANCELLED`
- `UPLOADING` -> `PAUSED`, `PROCESSING`, `PUBLISHED`, `FAILED`, `CANCELLED`, `REQUIRES_REAUTH`
- `PAUSED` -> `UPLOADING`, `CANCELLED`, `FAILED`
- `PROCESSING` -> `PUBLISHED`, `FAILED`
- `REQUIRES_REAUTH` -> `AUTHENTICATING`, `PENDING`, `CANCELLED`
- `PUBLISHED` -> (Son durum / Terminal state)
