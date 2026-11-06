# STAGE 6.7 — SON UI/UX DÜZELTMELERİ VE CREATOR STUDIO KAPANIŞI

**Tarih:** 2026-11-06  
**Başlangıç commit:** `fecef4e`  
**Dal:** `main`  
**Kapsam:** Kodlama + son kalite doğrulaması  
**Aşama durumu:** **PASS_WITH_NOTES**  
**Ürün durumu:** **READY_WITH_EXTERNAL_LIMITATIONS**

---

## 1. Amaç ve sınırlar

Bu aşamada yalnızca dört somut UI/UX sorunu ele alındı:

1. Platform yeteneklerinin ham teknik anahtarlarla gösterilmesi.
2. Analytics'in bağlantı düzeyinde API kapalı olmasına rağmen adaptör düzeyinde "Açık" görünmesi.
3. Dashboard'da devre dışı legacy kanalın aktif kanal sayısına dahil edilmesi.
4. Birincil kanal etiketlerinin yanlış veya yanıltıcı gösterilmesi.

Uygulanan sınırlar:

- Gerçek Google bağlantısı, token'lar, DB kayıtları ve legacy Keychain verileri değiştirilmedi.
- Gerçek YouTube kanalında yazma işlemi yapılmadı.
- Legacy DB kayıtları güncellenmedi veya silinmedi.
- UI/API hesaplamasıyla çözülebildiği için veritabanı migration'ı yapılmadı.
- Push/deploy yapılmadı.
- Yeni Stage 6.8, 6.9, 7.0 veya yeni audit alt aşaması üretilmedi.

---

## 2. Başlangıç bulguları

| Sorun | Kanıt |
| --- | --- |
| Ham capability anahtarları | `PlatformSettingsPage.tsx` yalnızca eski anahtarları biliyordu; `disconnect`, `list_accounts`, `list_channels`, `get_channel_profile`, `get_analytics`, `update_video`, `schedule_publish` için `CAPABILITY_LABELS[key] \|\| key` ham anahtarı gösteriyordu. |
| Analytics tutarsızlığı | Platform Ayarları yalnızca adaptör kataloğunu okuyordu; `get_analytics: true` her durumda "Açık" görünüyordu. Bağlı hesabın `api_not_enabled` durumu hesaba katılmıyordu. |
| Dashboard kanal sayısı | `GetGlobalDashboardUseCase` tüm kanalları sayıyordu. DB'de 2 kanal vardı; bunlardan `UC_RESILIENCE` devre dışıydı. Dashboard "Yönetilen kanal" 2 gösteriyordu. |
| Birincil etiket | `ConnectedAccountsPage` her `is_primary=true` kanal için "birincil" basıyordu. Devre dışı legacy kanal da birincil işaretli olduğu için yanıltıcı etiket oluşuyordu. |

---

## 3. Yapılan değişiklikler

### 3.1 Platform yetenekleri — okunabilir etiketler

**Dosya:** `frontend/src/pages/PlatformSettingsPage.tsx`

- Gerçek `PlatformCatalog` anahtarlarının tamamı Türkçe etiketlere eşlendi:
  - `connect_oauth` → Hesap bağlama
  - `disconnect` → Bağlantıyı kesme
  - `list_accounts` → Hesap listesi
  - `list_channels` → Kanal listesi
  - `get_channel_profile` → Kanal profili
  - `list_videos` → Video listesi
  - `upload_video` → Video yükleme
  - `update_video` → Video güncelleme
  - `get_analytics` → Analytics
  - `read_comments` → Yorum okuma
  - `write_comments` → Yorum yazma
  - `schedule_publish` → Planlı yayın
  - `monetization_revenue` → Gelir verisi
- Bilinmeyen capability anahtarı artık ham anahtar olarak gösterilmiyor; güvenli varsayılan `Tanımsız yetenek` etiketi kullanılıyor.
- Teknik anahtarlar API sözleşmesinde ve loglarda değiştirilmedi.

### 3.2 Analytics — adaptör desteği ile bağlantı durumu ayrımı

**Dosyalar:** `frontend/src/pages/PlatformSettingsPage.tsx`, `frontend/src/pages/AnalyticsPage.tsx`

- Platform Ayarları artık `listPlatforms()` ile birlikte `listConnections(false)` çağrısı yapıyor.
- Analytics satırında iki katman ayrı gösteriliyor:
  - **Adaptör desteği:** Analytics yeteneği destekleniyorsa "adaptör desteği var".
  - **Bağlantı durumu:** Bağlı hesabın `analytics` capability durumu.
- Durum eşlemesi:
  - `active` → Açık
  - `scope_required` → İzin gerekli
  - `api_not_enabled` → API kapalı
  - `reauth_required` → Yeniden bağlan
  - `unavailable` → Kullanılamıyor
- `api_not_enabled` durumunda:
  - Analytics "Açık" veya "Hazır" gösterilmiyor.
  - İzin verme (grant) düğmesi sunulmuyor.
  - Google Cloud Console yönlendirmesi korunuyor.
  - Sahte veri üretilmiyor.
- Bağlantı durumu yalnızca adaptörün Analytics'i desteklediği platformlara uygulanıyor; Instagram/TikTok gibi pasif platformlarda "API kapalı" yanlış etiketi oluşmuyor.
- Analytics sayfasındaki alt durum etiketi ham `api_not_enabled` yerine "Analytics · API kapalı" olarak gösteriliyor.

### 3.3 Dashboard — yalnızca etkin kanal sayımı

**Dosya:** `backend/src/tezlify_studio/application/use_cases/get_global_dashboard_use_case.py`

- Bağlantı bazında kanallar `is_enabled` ile filtreleniyor.
- `totals.channels`, platform `channels`, hesap `channel_count` ve hesap kanal listesi yalnızca etkin kanalları içeriyor.
- Hesap DTO'suna açıkça `channel_count` eklendi; böylece arayüzde eksik/`undefined` kanal sayısı oluşmuyor.
- Devre dışı legacy kanal DB'de korunuyor; yalnızca Dashboard sayımından ve listesinden dışlanıyor.

### 3.4 Birincil kanal etiketi

**Dosya:** `frontend/src/pages/ConnectedAccountsPage.tsx`

- Her bağlantı için `is_primary && is_enabled` koşulunu sağlayan ilk kanal belirleniyor.
- "birincil" etiketi yalnızca bu kanalda gösteriliyor.
- Birden fazla etkin `is_primary=true` olsa bile tek etiket gösteriliyor.
- Devre dışı legacy kanal birincil olarak etiketlenmiyor.
- Kanal seçimi kalıcılığı (`tezlify.active_channel_id`) ve devre dışı kanalın seçiciden dışlanması korunuyor.

---

## 4. Eklenen regresyon testleri

### Backend

**Yeni dosya:** `backend/tests/unit/test_global_dashboard_use_case.py`

1. `test_dashboard_counts_only_enabled_channels`
   - Etkin + devre dışı kanal birlikte verildiğinde `totals.channels`, platform `channels`, `channel_count` ve hesap kanal listesinin yalnızca etkin kanalı içerdiğini doğrular.
2. `test_dashboard_without_enabled_channels_reports_zero`
   - Yalnızca devre dışı kanal olduğunda tüm kanal sayılarının 0 olduğunu doğrular.

### Frontend

**Dosya:** `frontend/src/pages/CapabilityPermissions.test.tsx`

1. Tüm capability'lerin Türkçe etiketlerle gösterildiği ve bilinmeyen anahtarın ham olarak basılmadığı doğrulanır.
2. `api_not_enabled` durumunda Analytics'in "API kapalı" gösterdiği, "Açık"/"Adaptör destekliyor" göstermediği ve Google Cloud yönlendirmesinin korunduğu doğrulanır.
3. Bağlantı Analytics durumunun pasif platformlara kopyalanmadığı doğrulanır.
4. Birden fazla etkin birincil kanalda yalnızca bir "birincil" etiketi gösterildiği doğrulanır.
5. Devre dışı legacy birincil kanalın etiketlenmediği doğrulanır.
6. Mevcut Analytics testi, ham `api_not_enabled` metninin arayüzde görünmediğini ve "Analytics · API kapalı" gösterildiğini doğrular.

---

## 5. Kalite kapısı

| Kontrol | Komut | Sonuç |
| --- | --- | --- |
| Backend testleri | `env -u NO_PROXY -u no_proxy .venv/bin/python -m pytest backend/tests -q` | **199 passed**, 1 uyarı |
| Frontend testleri | `npm test` | **23 passed** (3 dosya) |
| TypeScript + production build | `npm run build` | **PASS** (`tsc && vite build`, 1543 modül) |
| Diff whitespace | `git diff --check` | **PASS** |
| Secret scan | Değişen dosyalarda token/secret deseni taraması | **PASS** (eşleşme yok) |

**Not:** Backend testleri çalıştırılırken ortamda bulunan `NO_PROXY=[::1]` değeri `httpx` tarafından geçersiz port olarak ayrıştırıldığı için komut `NO_PROXY`/`no_proxy` kaldırılarak çalıştırıldı. Bu bir kod regresyonu değildir; testler bu ortam değişkeni olmadan tamamen geçmiştir.

---

## 6. Gerçek DB ile salt okunur UI kabulü

Uygulama gerçek `data/database/tezlify_studio.db` ve mevcut Google bağlantısıyla başlatıldı. Hiçbir yazma, OAuth veya token işlemi yapılmadı.

### Platform Ayarları

- YouTube yetenekleri Türkçe etiketlerle gösterildi.
- Analytics satırı: **"Analytics — adaptör desteği var — API kapalı"**.
- Google Cloud Console yönlendirmesi görünür.
- Instagram/TikTok Analytics satırları **"Kapalı"** gösterdi; YouTube bağlantı durumu bu platformlara kopyalanmadı.
- Ham `get_analytics`, `get_channel_profile`, `mystery_capability` benzeri anahtar DOM'da bulunmadı.

### Genel Panel (Dashboard)

- Bağlı hesap: **1**
- Yönetilen kanal: **1**
- Platform özeti: **1 hesap · 1 kanal**
- Bağlı hesap kartı: **1 kanal**
- Devre dışı `Resilience Channel` / `UC_RESILIENCE` sayıma dahil edilmedi.

### Bağlı Hesaplar

- Tek bir **"birincil"** etiketi gösterildi; bu etiket etkin `İsa Tezcan` kanalındaydı.
- Devre dışı legacy `Resilience Channel` için "birincil" etiketi gösterilmedi.
- Legacy kanal yönetim listesinde görünmeye devam ediyor ancak "Yönetimde" kutusu işaretsiz.

### Analytics

- **"YouTube Analytics API etkin değil"** durumu gösterildi.
- Google Cloud Console yönlendirmesi görünür.
- Analytics izni verme düğmesi sunulmadı.
- Durum etiketi **"Analytics · API kapalı"**; ham `api_not_enabled` metni DOM'da yok.

### Konsol ve ağ

- Tarayıcı konsolunda yalnızca Vite/React geliştirme bilgi mesajları vardı; hata yok.
- Sayfa yüklemesindeki tüm API istekleri **HTTP 200** döndü; 5xx yok.

### Kanal seçimi kalıcılığı

- `localStorage["tezlify.active_channel_id"]` = etkin kanal kimliği.
- `/api/v1/channels` yalnızca etkin kanalı döndürdü (`total=1`); devre dışı legacy kanal seçicide yok.
- Sayfa yenilemesinden sonra seçim korundu.

---

## 7. Veri ve anahtar zinciri bütünlüğü

| Kontrol | Sonuç |
| --- | --- |
| `PRAGMA integrity_check` | `ok` |
| `platform_connections` | 1 |
| `platform_channels` | 2 |
| Etkin kanal | 1 |
| Legacy `UC_RESILIENCE` | `is_enabled=0`, `is_primary=1` (değiştirilmedi) |
| `scheduled_publishes` | 0 |
| `publish_records` | 135 |
| `media_assets` | 324 |
| `upload_sessions` | 0 |
| Keychain `TezlifyStudio_access` — aktif hesap | PRESENT |
| Keychain `TezlifyStudio_refresh` — aktif hesap | PRESENT |
| Keychain `TezlifyStudio_access` — legacy `f9183de5-…` | PRESENT |
| Keychain `TezlifyStudio_refresh` — legacy `f9183de5-…` | PRESENT |

Token değerleri okunmadı, gösterilmedi ve değiştirilmedi.

---

## 8. Notlar ve kalan dış sınırlamalar

1. **Analytics API hâlâ harici kullanıcı işlemi gerektiriyor.** Google Cloud projesinde YouTube Analytics API etkin değil. Bu kodla çözülemez; Google Cloud Console üzerinden etkinleştirilmelidir.
2. **Analytics kullanılabilirliği gözleme dayalıdır.** Bağlantı capability durumu, gerçek Analytics çağrısı sonrasında `api_not_enabled` olarak işaretlenir. Platform Ayarları adaptör düzeyinde hiçbir zaman "Açık" demez; bağlantı durumu bilinmiyorsa "Adaptör destekliyor" gösterir. API kapalı durumu gözlemlendiğinde tüm ilgili ekranlar "API kapalı" gösterir.
3. **Yazma yolları bu aşamada gerçek YouTube üzerinde test edilmedi.** Upload, yorum gönderme/moderasyon ve planlı yayın gerçek yazma işlemleri kapsam dışıdır ve mevcut mock/izolasyon testleriyle korunmaktadır.
4. **Ekran görüntüsü alınamadı.** Bu oturumda in-app Browser görünür yüzeyi (viewport 0x0) sağlamadığı için görsel kabul DOM metni, konsol ve ağ kayıtlarıyla yapıldı; yapısal doğrulama tamamlandı.
5. Legacy devre dışı kanal, yönetim amacıyla Bağlı Hesaplar ekranında görünmeye devam eder; Dashboard sayımından ve kanal seçicisinden dışlanmıştır.

---

## 9. Değişen dosyalar

- `backend/src/tezlify_studio/application/use_cases/get_global_dashboard_use_case.py`
- `backend/tests/unit/test_global_dashboard_use_case.py` (yeni)
- `frontend/src/pages/PlatformSettingsPage.tsx`
- `frontend/src/pages/AnalyticsPage.tsx`
- `frontend/src/pages/ConnectedAccountsPage.tsx`
- `frontend/src/pages/CapabilityPermissions.test.tsx`

**Commit mesajı:** `fix(studio): polish creator studio final ui states`

---

## 10. Sonuç

Dört UI/UX sorunu da minimum kapsamda düzeltildi ve regresyon testleriyle korundu. Backend/frontend test paketleri, TypeScript derlemesi, production build, gerçek DB salt okunur UI kabulü, konsol/ağ kontrolü, DB bütünlüğü, Keychain varlığı ve secret taraması geçti.

**Aşama sonucu:** **PASS_WITH_NOTES**  
**Ürün sonucu:** **READY_WITH_EXTERNAL_LIMITATIONS** — Creator Studio kullanıma hazırdır; YouTube Analytics verisi, Google Cloud projesinde YouTube Analytics API etkinleştirilene kadar harici bir kullanıcı işlemi nedeniyle kullanılamaz.
