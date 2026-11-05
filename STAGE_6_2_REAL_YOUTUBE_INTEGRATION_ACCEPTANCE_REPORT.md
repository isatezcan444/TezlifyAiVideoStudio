# TEZLIFY CREATOR STUDIO — STAGE 6.2 — GERÇEK YOUTUBE OAUTH, KANAL KEŞFİ VE CANLI READ-ONLY KABUL RAPORU

**Aşama:** 6.2 — Gerçek YouTube OAuth, Kanal Keşfi ve Canlı Read-Only Kabul
**Tür:** KODLAMA + GERÇEK ORTAM DOĞRULAMASI
**Tarih:** 2026-11-05 (yerel 23:15–23:30, UTC 20:15–20:30)
**Başlangıç SHA:** `83e8e59fa1b0dc94ec85231c7505f6f355fa58d9` — `feat(studio): support multiple platform accounts and youtube channels`
**Bitiş SHA:** Bu raporun yer aldığı son yerel commit — `test(studio): verify real youtube account integration` (hash: `git log -1 --format=%H`)
**Sonuç:** **PASS_WITH_NOTES**

---

## 1. Yönetici Özeti

Stage 6.1'de kurulan çok hesaplı / çok kanallı mimari, gerçek Google hesabı ve gerçek YouTube kanalı ile read-only olarak doğrulandı:

- Mevcut Google hesabı yeniden yetkilendirildi; gerçek kimlik (`google:114116763129284035467`) ve gerçek kanal (`UCtxeOcY7FyvxiWXgo3CQE4Q`, `İsa Tezcan`, `@isatezcan7767`) keşfedildi.
- `platform_connections` kaydı yeniden kullanıldı (yeni satır oluşmadı); migration'dan kalan `legacy:` kimliği gerçek Google subject'i ile yerinde güncellendi.
- Migration'dan kalan `UC_RESILIENCE` placeholder kanalı silinmedi; aynı bağlantı altında korunup `is_enabled=0` yapıldı.
- Dashboard gerçek Data API verisini gösterdi; Analytics API `api_not_enabled` nedeniyle kapalı kaldı ve **hiçbir sahte değer üretilmedi**.
- Kanal seçimi yeniden yükleme sonrası korundu; kanal değişiminde önceki kanalın verisi ekranda kalmadı.
- Gerçek kanala hiçbir yükleme, yorum, metadata değişikliği veya yayın işlemi yapılmadı.
- Tüm yayın/medya kayıtları korundu; `PRAGMA integrity_check=ok`, `foreign_key_check` boş.

`PASS` yerine `PASS_WITH_NOTES` verilmesinin üç kanıtlı nedeni:

1. **YouTube Analytics API**, kullanıcının Google Cloud projesinde etkin değil (`accessNotConfigured` / `api_not_enabled`). Bu bir izin değil, proje yapılandırması sorunudur ve kullanıcı müdahalesi (Google Cloud Console → API'yi etkinleştir) gerektirir.
2. **İkinci Google hesabı** bu makinede mevcut olmadığı için gerçek ikinci hesapla çoklu hesap kabulü yapılamadı. Mimari, fake portlarla izole biçimde test edildi; gerçek ikinci hesap testi kullanıcı müdahalesi gerektiriyor.
3. 135 eski yayın kaydı, migration'ın tek hesap varsayımıyla `legacy_single_account` olarak işaretli ve placeholder `UC_RESILIENCE` kanalına bağlı. Gerçek kanalla bire bir eşleşme kanıtı yok; bu aşamada mevcut kayıtlar **değiştirilmedi**. Risk ve öneri §12'de.

---

## 2. Kapsam ve Uygulanan Kısıtlar

Bu aşamada:

- Gerçek YouTube kanalına **hiçbir yazma işlemi** yapılmadı (upload, yorum, metadata, publish yok).
- Kullanıcı adına OAuth onayı veya Google şifresi işlemi **agent tarafından** gerçekleştirilmedi; onay adımını kullanıcı tarayıcıda tamamladı.
- Eski token bulunamadığı için **sahte token üretilmedi**; güvenli yeniden yetkilendirme yapıldı.
- Token değerleri loglanmadı, frontend'e gönderilmedi, rapora yazılmadı.
- Google OAuth client secret değerleri rapora yazılmadı.
- Keychain içeriği (şifre/token) okunup rapora yazılmadı; yalnızca öğe varlığı ve hesap referansı doğrulandı.
- Gerçek veritabanında destructive migration yapılmadı; migration çalıştırılmadı (revizyon zaten `d61a0c1f4b2e`).
- Mevcut yayın ve medya kayıtları değiştirilmedi.
- Yeni sosyal medya platformu eklenmedi; video üretim özellikleri geri getirilmedi.
- Yalnızca yerel commit oluşturuldu; push ve deployment yapılmadı.

---

## 3. Başlangıç Durumu ve Ortam

| Bileşen | Değer |
|---|---|
| Alembic revizyonu | `d61a0c1f4b2e` |
| Backend | FastAPI, `127.0.0.1:8000`, `SCHEDULER_ENABLED=false` |
| Frontend | Vite dev server, `127.0.0.1:5173` |
| Veritabanı | `data/database/tezlify_studio.db` (SQLite WAL) |
| Tarayıcı doğrulaması | browser-use MCP (snapshot/click) |

Aşama başında tespit edilen gerçek engel: mevcut bağlantının `token_reference` değeri ile Keychain'de duran hesap referansı uyuşmuyordu. Keychain'de `TezlifyStudio_access` / `TezlifyStudio_refresh` öğeleri eski `f9183de5-…` referansı altında bulunuyordu; aktif bağlantının referansı `103d53ec-…` idi ve bu referansta öğe yoktu. Bu nedenle eski token'lar sahiplenilmedi veya tahmin edilmedi; kullanıcı onayıyla güvenli yeniden yetkilendirme yapıldı.

---

## 4. Gerçek OAuth ve Yeniden Yetkilendirme

Kullanıcı, tarayıcıda Google onay ekranını tamamladı. Uygulama tarafında:

- PKCE + tek kullanımlık `state` ile loopback callback işlendi.
- Bağlantı kaydı **yerinde güncellendi** (yeni hesap satırı oluşmadı).
- `account_external_id`: `legacy:UC_RESILIENCE` → `google:114116763129284035467`
- `account_display_name`: `İsa Tezcan`
- `connection_status`: `active`
- `token_reference`: `103d53ec-61da-4fa7-b0f7-96955ab8314c` (değişmedi)
- `token_expires_at`: `2026-11-05 21:15:45` (UTC)
- Bağlantı oluşturulma zamanı: `2026-11-04 22:11:01` (migration), güncellenme: `2026-11-05 20:15:46` — yani yeni satır değil, yerinde upgrade.

**OAuth onayı sonrası `ERR_CONNECTION_REFUSED` notu:** Başarı sayfası ("Yetkilendirme Başarılı") render edildikten sonra tek kullanımlık loopback listener kapanıyor; sayfa yeniden yüklenirse bağlantı reddedilir. Bu bir OAuth hatası değildir; callback, veritabanı ve Keychain kaydı başarıyla tamamlanmıştır. Kullanıcıya sayfa yenilememesi gerektiği not edilmelidir.

### 4.1 Verilen gerçek OAuth kapsamları (7)

`granted_scopes_json` alanından okunan gerçek kapsamlar:

1. `openid`
2. `https://www.googleapis.com/auth/userinfo.email`
3. `https://www.googleapis.com/auth/userinfo.profile`
4. `https://www.googleapis.com/auth/youtube.readonly`
5. `https://www.googleapis.com/auth/youtube.upload`
6. `https://www.googleapis.com/auth/yt-analytics.readonly`
7. `https://www.googleapis.com/auth/youtube.force-ssl`

Geniş `https://www.googleapis.com/auth/youtube` kapsamı bu aşamada koddan çıkarıldı (bkz. §9). `youtube.upload` ve `youtube.force-ssl` ilerideki yayın/yorum yetenekleri için korunmuştur; bu aşamada kullanılmadı.

---

## 5. Gerçek Kanal Keşfi

`channels.list?part=snippet,statistics,contentDetails&id=UCtxeOcY7FyvxiWXgo3CQE4Q` ile doğrulanan gerçek kanal:

| Alan | Değer |
|---|---|
| Kanal ID | `UCtxeOcY7FyvxiWXgo3CQE4Q` |
| Ad | `İsa Tezcan` |
| Handle | `@isatezcan7767` |
| Yayın tarihi | `2014-08-15T10:36:01Z` |
| Abone | `0` (gizli değil) |
| Video / görüntüleme | `0` / `0` |
| Uploads playlist | `UUtxeOcY7FyvxiWXgo3CQE4Q` |
| Avatar | `https://yt3.ggpht.com/...` (gerçek kanal avatarı) |

Veritabanındaki kanal kayıtları:

| Kanal | Harici ID | Durum |
|---|---|---|
| `d1bb27b003dd41ea91227107e2df730d` | `UCtxeOcY7FyvxiWXgo3CQE4Q` | `is_enabled=1`, `is_primary=1` |
| `5d26da930c7ee0ffc9556f9894080483` | `UC_RESILIENCE` | `is_enabled=0`, korunuyor |

Keşif sırasında `_upsert_channels`, keşfedilen kanallar dışında kalan mevcut kanalı silmedi; yalnızca `is_enabled=0` yaptı. Bu, 6.1'deki "bilinmeyen kaydı silme/tahmin etme" ilkesiyle uyumludur.

Aktif seçim: `user_channel_preferences('default') → d1bb27b003dd41ea91227107e2df730d`, platform `youtube`.

---

## 6. Read-Only API Doğrulaması (gerçek veri)

Tüm sonuçlar 2026-11-05 ~20:23 UTC'de canlı backend'den yeniden ölçülmüştür.

### 6.1 Dashboard (`GET /api/v1/dashboard?range=28`)

- `connected: true`
- Kanal profili gerçek kanal; `source: youtube_data_api`
- `subscriber_count=0`, `video_count=0`, `view_count=0`
- `analytics.available: false`, `analytics.reason: "api_not_enabled"`, `totals: {}`
- `local_counts.scope: "channel"`, `total_publish_records: 0`, `upcoming_schedule_count: 0`
- Son video: `1DMEIRsLUD0`, `[TEST] Tezlify AI Video Studio Verification`, `private`, 16 sn, 1 görüntüleme
- Kaynak etiketleri: abone/görüntüleme/video → Data API; günlük analitik → Analytics API; planlama/geçmiş → yerel DB
- `warnings: []`

### 6.2 Kanal overview (`GET /api/v1/channels/youtube/overview`)

Gerçek profil, `published_at`, abone/video/görüntüleme sayıları ve uploads playlist döndü; `source: youtube_data_api`. Oynatma listeleri: `[]`.

### 6.3 Videolar (`GET /api/v1/channels/youtube/videos?max_results=10`)

- `total_results: 2`
- Dönen öğe: `1DMEIRsLUD0`, `private`, 16 sn, 1 görüntüleme
- Sahte video ID'si üretilmedi.

### 6.4 Analytics (`GET /api/v1/channels/youtube/analytics?range=28&dimensions=day`)

- `available: false`, `reason: "api_not_enabled"`
- `explanation`: "YouTube Analytics API bu Google Cloud projesinde etkin değil. Google Cloud Console üzerinden API'yi etkinleştirmeniz gerekir."
- `totals: {}`, `rows: []`, `revenue: null`
- Kapsam (`yt-analytics.readonly`) verilmiş olmasına rağmen API proje düzeyinde kapalı olduğu için `insufficient_scope` değil `api_not_enabled` sınıflandırması doğru çalıştı.

### 6.5 Bağlantılar (`GET /api/v1/social/connections`)

Tek aktif bağlantı: `İsa Tezcan`, `active`, iki kanal:

- `UC_RESILIENCE` / `Resilience Channel` — `is_enabled=false`
- `UCtxeOcY7FyvxiWXgo3CQE4Q` / `İsa Tezcan` / `@isatezcan7767` — `is_enabled=true`

`GET /api/v1/channels` yalnızca etkin kanalı döndürür (`total: 1`); devre dışı placeholder global seçiciye sızmaz.

---

## 7. Keychain İzolasyonu

Yalnızca öğe varlığı ve hesap referansı kontrol edildi; **hiçbir token değeri okunmadı veya yazdırılmadı**.

| Servis | Hesap referansı | Durum |
|---|---|---|
| `TezlifyStudio_access` | `103d53ec-…` | mevcut |
| `TezlifyStudio_refresh` | `103d53ec-…` | mevcut |
| `TezlifyStudio_access` | `f9183de5-…` | mevcut (eski/orphan) |
| `TezlifyStudio_refresh` | `f9183de5-…` | mevcut (eski/orphan) |

- Yeni token'lar doğru bağlantı referansı (`103d53ec-…`) altında yazıldı.
- Eski `f9183de5-…` öğeleri okunmadı, silinmedi ve başka hesaba kopyalanmadı.
- Token'lar kanal ID'siyle değil, bağlantı referansıyla anahtarlanır; bu, tek Google hesabı altındaki çoklu kanal için doğru izolasyon modelidir.

**Not:** Eski `f9183de5-…` öğeleri orphan kalmıştır. Bu aşamada silinmedi (veri kaybı riski ve kullanıcı onayı gereksinimi). Gelecekte kullanıcı onayıyla temizlenebilir.

---

## 8. UI Kabul Testi

browser-use MCP ile canlı frontend üzerinde doğrulandı:

| Ekran / Akış | Gözlem | Sonuç |
|---|---|---|
| Kanal switcher | `İSA TEZCAN`, `@isatezcan7767`; ekleme seçeneği mevcut | PASS |
| Kanal dashboard | Gerçek avatar/ad/handle, Data API etiketleri, Analytics kapalı mesajı, son video | PASS |
| Analytics sayfası | API'nin projede kapalı olduğunu doğru açıklıyor | PASS |
| Bağlı Hesaplar | 1 aktif hesap, 2 kanal; `Resilience` devre dışı, gerçek kanal etkin | PASS |
| Global Panel | 1 hesap, 2 yönetilen kanal, 135 yayın kaydı, 0 planlı; unresolved uyarısı yok | PASS |
| Upload hedefi | `İsa Tezcan` / `@isatezcan7767` / bağlantı aktif; seçili kanalda boş yayın geçmişi | PASS |
| Scheduler hedefi | "Hedef kanal: İsa Tezcan" | PASS |
| Sayfa yenileme sonrası seçim | `localStorage` + sunucu tercihi ile aynı kanal korunuyor | PASS |
| Kanal değişiminde veri sızıntısı | Önceki kanalın dashboard verisi kalmıyor; yeni kanal için 0 kayıt | PASS |
| Loading / empty / error | Analytics kapalıyken "Kullanılamıyor" + açıklama; boş listelerde empty state; hata durumunda uyarı | PASS |

**Dashboard mesaj düzeltmesi:** Önceden Analytics kapalıyken dashboard "Analitik izni gerekli" diyordu; bu, proje düzeyindeki `api_not_enabled` durumunu yanlışlıkla izin sorunu gibi gösteriyordu. Artık `analytics.reason` değerine göre:

- `api_not_enabled` → Google Cloud Console'da API'yi etkinleştirme yönlendirmesi
- `insufficient_scope` → Bağlı Hesaplar üzerinden yeniden yetkilendirme
- `quota_exceeded` → kota mesajı
- diğer → genel kullanılamıyor mesajı

Canlı UI'da doğrulanan yeni metin: "YouTube Analytics API kapalı" ve "YouTube Analytics API bu Google Cloud projesinde etkin değil. Google Cloud Console üzerinden API'yi etkinleştirmeniz gerekir."

---

## 9. Yapılan Kod Düzeltmeleri

### 9.1 En az yetki OAuth kapsamları

**Commit:** `03775fbfaf9bf14289e9c12642a0b90ce8695df3` — `fix(studio): request least-privilege youtube oauth scopes`

`YOUTUBE_SCOPES` listesinden geniş `https://www.googleapis.com/auth/youtube` kaldırıldı. Kalan kapsamlar gerçek entegrasyonun ihtiyaç duyduğu 7 kapsamdır. Böylece uygulama, ihtiyaç duymadığı geniş YouTube yetkisini talep etmez.

### 9.2 Gerçek Analytics nedeniyle uyumlu dashboard mesajı

**Commit:** `dad14c0e184f48f1356b3432ad5788e44f05e4a8` — `fix(studio): surface real youtube analytics availability reason`

`DashboardPage.tsx` içinde sabit "Analitik izni gerekli" metni, backend'in döndürdüğü `reason` değerine göre eşlenen mesajlarla değiştirildi. Sahte veri veya yanlış izin suçlaması üretilmiyor.

---

## 10. Test Sonuçları

### 10.1 Backend

Komut: `.venv/bin/python -m pytest backend/tests -q`

**Sonuç: 151 passed, 1 warning (9.49s)** — Stage 6.1'deki 135 testin üzerine 16 yeni test eklendi.

Yeni kapsam:

- En az yetki OAuth kapsam sözleşmesi (geniş `auth/youtube` yok)
- Legacy bağlantının gerçek kimlikle yerinde upgrade'i; token referansının korunması
- Yeni gerçek hesabın legacy bağlantıya dokunmaması; ayrı token referansı
- Yeniden keşifte kaldırılan kanalın silinmemesi, yalnızca devre dışı bırakılması
- Tekrarlı keşfin kanal ID'lerini çoğaltmaması
- Token referansının kanal ID'si değil bağlantı ID'si olması
- İki hesap arasında token izolasyonu ve tek hesabın token silinmesinin diğerini etkilememesi
- Gateway'in her istekte kanal başına ayrı adapter bağlaması
- Dashboard'un `api_not_enabled` nedenini koruması ve `totals={}` ile sahte veri üretmemesi
- Analytics hatasının uyarıya dönüşmesi, sahte veriye değil
- Dashboard'un önceki kanal durumunu yeniden kullanmaması
- Frontend'in `api_not_enabled` için doğru açıklama göstermesi
- Analytics 403 `accessNotConfigured` → `api_not_enabled`
- Analytics 401 → yeniden kimlik doğrulama istisnası
- Gerçek keşif payload'unun kanal profiline eşlenmesi
- Kanal bulunamadığında binding mismatch

### 10.2 Frontend

- `npm test`: **4 passed**
- `npm run build` (`tsc && vite build`): **başarılı**, 1541 modül dönüştürüldü

---

## 11. Veri Güvenliği ve Koruma Kanıtı

Ölçüm: 2026-11-05 ~20:24 UTC, canlı DB.

| Tablo | Kayıt |
|---|---|
| `studio_projects` | 236 |
| `media_assets` | 324 |
| `publish_records` | 135 |
| `social_accounts` | 1 |
| `render_jobs` | 99 |
| `video_compositions` | 52 |
| `studio_assets` | 15 |
| `characters` | 4 |
| `scheduled_publishes` | 0 |
| `platform_connections` | 1 |
| `platform_channels` | 2 |
| `user_channel_preferences` | 1 |

- `PRAGMA integrity_check`: `ok`
- `PRAGMA foreign_key_check`: boş
- Alembic revizyonu: `d61a0c1f4b2e` (değişmedi)
- Yayın/medya kayıtlarında silme veya güncelleme yapılmadı.
- Migration öncesi yedekler mevcut: `tezlify_studio_backup_20261105T152520Z.db`, `tezlify_studio_pre_stage6_1_20261105T152524Z.db`.

---

## 12. Bilinen Sınırlamalar ve Kullanıcı Müdahale Noktaları

1. **YouTube Analytics API kapalı (BLOCKER değil, kullanıcı aksiyonu).**
   Google Cloud Console → APIs & Services → Library → "YouTube Analytics API" → Enable. Ardından Analytics sayfası yenilendiğinde gerçek veri görünmelidir. Kod ve izin tarafında eksik yoktur.
2. **İkinci Google hesabı gerçek ortamda test edilmedi.**
   Bu makinede erişilebilir ikinci bir Google hesabı yoktu. Sahte hesap üretilmedi. Çoklu hesap izolasyonu fake portlarla 16 testte doğrulandı; gerçek ikinci hesap kabulü için kullanıcının "Hesap / Kanal Ekle" akışını kendi ikinci hesabıyla tamamlaması gerekir.
3. **135 legacy yayın kaydı.**
   Tümü `channel_attribution='legacy_single_account'` ve placeholder `UC_RESILIENCE` kanalına bağlı. 27 kayıtta yalnızca `mock_yt_vid_42` gibi mock harici ID var; 108 kayıtta harici ID yok. Gerçek kanalla bire bir eşleşme kanıtı bulunmadığından bu aşamada **kayıtlar değiştirilmedi**. Gerçek kanalın yayın geçmişi doğru biçimde 0 gösteriyor. İleride kullanıcı onayıyla bu kayıtlar `unresolved` olarak işaretlenebilir veya kanıtlı eşleşme yapılabilir.
4. **Eski Keychain öğeleri (`f9183de5-…`) orphan.**
   Silinmedi; kullanıcı onayıyla ayrı bir temizlik adımında kaldırılabilir.
5. **Loopback listener tek kullanımlık.**
   OAuth başarı sayfasından sonra tarayıcı yenilenirse `ERR_CONNECTION_REFUSED` görülür; bu beklenen davranıştır. Bağlantı zaten tamamlanmıştır.
6. **Gerçek kanalda yazma işlemleri kapsam dışı.**
   Upload, yorum, metadata ve publish için ayrıca kullanıcı onayı gerekir; bu aşamada hiçbiri yapılmadı.

---

## 13. Kabul Kriterleri Tablosu

| Kriter | Sonuç | Kanıt |
|---|---|---|
| Gerçek Google hesabı güvenli yeniden bağlandı | PASS | `google:114116763129284035467`, `active`, yerinde upgrade |
| Gerçek kanal keşfedildi ve doğrulandı | PASS | `UCtxeOcY7FyvxiWXgo3CQE4Q`, `@isatezcan7767` |
| Kanal ID / profil doğru | PASS | Overview + DB + UI |
| Çoklu hesap OAuth akışı | PASS_WITH_NOTES | Mimari testler PASS; gerçek 2. hesap yok |
| Gerçek dashboard verisi | PASS | Data API sayıları, son video |
| Analytics verisi | BLOCKED (dış yapılandırma) | `api_not_enabled`, doğru mesaj, sahte veri yok |
| OAuth kapsamları | PASS | 7 kapsam, geniş `auth/youtube` çıkarıldı |
| Keychain izolasyonu | PASS | Doğru referans; eski öğeler okunmadı |
| Hesap yöneticisi UI | PASS | 1 hesap, 2 kanal, doğru durumlar |
| Global kanal seçici | PASS | Etkin kanal listeleniyor; devre dışı kanal sızmıyor |
| Yeniden başlatma sonrası kalıcılık | PASS | Reload sonrası aynı kanal |
| Kanallar arası veri sızıntısı yok | PASS | Kanal başına 0 kayıt; önceki veri kalmıyor |
| Upload / scheduler hedefi | PASS | `İsa Tezcan`, `@isatezcan7767` |
| Gerçek kanala yazma yok | PASS | Hiçbir yazma çağrısı yapılmadı |
| Mevcut veriler korundu | PASS | Sayımlar, integrity, FK |
| Testler | PASS | 151 backend, 4 frontend, build başarılı |
| Yalnızca yerel commit | PASS | Push/deploy yok |

---

## 14. Commit Planı

| Commit | Mesaj | Kapsam |
|---|---|---|
| `03775fb` | `fix(studio): request least-privilege youtube oauth scopes` | `youtube_creator_api.py` |
| `dad14c0` | `fix(studio): surface real youtube analytics availability reason` | `DashboardPage.tsx` |
| rapor commit | `test(studio): verify real youtube account integration` | `test_real_youtube_stage62.py`, adapter testleri, bu rapor |

`STAGE_5_*` raporları, `evidence/**`, `backend/uv.lock` ve `data/database/backups/` Stage 6.2 commit'lerine dahil edilmedi. Push veya deployment yapılmadı.

---

## 15. Sonuç

**PASS_WITH_NOTES**

Gerçek YouTube hesabı ve kanalıyla read-only entegrasyon çalışıyor; çok hesaplı/çok kanallı mimari veri kaybı ve kanal sızıntısı olmadan doğrulandı. Analytics verisi, Google Cloud projesinde YouTube Analytics API etkin olmadığı için alınamıyor; bu, kod veya izin hatası değil, kullanıcı tarafından giderilmesi gereken bir yapılandırma eksikliğidir. İkinci gerçek hesap testi de kullanıcı müdahalesi beklemektedir. Bu iki nokta giderilene kadar sonuç `PASS` olarak raporlanmamalıdır.
