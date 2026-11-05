# TEZLIFY CREATOR STUDIO — STAGE 6.3
## Analytics Aktivasyonu, Çoklu Hesap Gerçek Kabulü ve OAuth Yetki Sertleştirmesi

**Tarih:** 5 Kasım 2026
**Repository:** `/Users/isatezcan/Documents/Github/Tezlify-AI-Video-Studio`
**Branch:** `main`
**Başlangıç commit'i:** `5d0e3a2` (`test(studio): verify real youtube account integration`)
**Çalışma türü:** Kodlama + gerçek ortam doğrulaması (salt okunur kabul)
**Push / deployment:** Yapılmadı.

---

## 1. Yönetici Özeti

| Madde | Sonuç | Gerekçe |
|---|---|---|
| YouTube Analytics API aktivasyonu ve gerçek veri | **BLOCKED** | API hâlâ `api_not_enabled`. Gerçek Analytics kabulü yapılamadı; kullanıcı Google Cloud Console'da API'yi etkinleştirmeli. |
| Çoklu hesap / çoklu kanal gerçek kabulü | **PASS_WITH_NOTES** | Tek gerçek Google hesabı var; aynı bağlantı altında iki kanal doğrulandı. İkinci Google hesabıyla gerçek kabul yapılamadı. İzolasyon sözleşmesi testlerle doğrulandı. |
| OAuth yetki sertleştirmesi | **PASS** | Yetenek bazlı scope grupları tanımlandı, `include_granted_scopes=true` eklendi, gelir scope'u opsiyonel ayrıldı. Mevcut token'lar geçersiz kılınmadı. |
| Dashboard / video listesi tutarsızlığı | **PASS** | `videoCount=0` (yalnızca herkese açık) ile uploads listesi `totalResults=2` farkı kanıtlandı, UI açıklaması ve sözleşme testi eklendi. |
| Legacy kayıt + Keychain güvenliği | **PASS** | 135 kayıt test verisi olarak kanıtlandı; hiçbir kayıt/token silinmedi veya taşınmadı. Temizlik ayrı onay önerisi olarak dokümante edildi. |

**Genel sonuç: `PASS_WITH_NOTES`**
Analytics gerçek kabulü kullanıcı aksiyonu gerektirdiği için o alt madde `BLOCKED`; diğer maddeler doğrulandı. Gerçek ortamda doğrulanmayan hiçbir maddeye PASS verilmedi.

---

## 2. Kısıt Uyumu

- Tezlify ana repository'sine dokunulmadı; yalnızca bu repository'de çalışıldı.
- Gerçek Google hesabının bağlantısı kesilmedi.
- Keychain token'ları silinmedi, kopyalanmadı, taşınmadı; yalnızca varlık kontrolü yapıldı (`security find-generic-password`, secret okunmadan).
- Gerçek kanal üzerinde upload, publish, delete, yorum, yanıt, playlist veya metadata değişikliği yapılmadı.
- Google Cloud Console ayarları kullanıcı adına değiştirilmedi.
- Token, refresh token, client secret, authorization code veya kişisel gizli veri loglanmadı.
- Gerçek veritabanında yıkıcı işlem yapılmadı; tüm DB sorguları `mode=ro` ile çalıştırıldı.
- Push veya deployment yapılmadı.
- Sahte hesapla gerçek kabul testi yapılmış gibi raporlanmadı.
- Mock testleri gerçek API kabulü sayılmadı; ayrı bölümde raporlandı.

---

## 3. Başlangıç Durumu

`2026-11-05T20:44Z` itibarıyla:

- Branch `main`, HEAD `5d0e3a2`, izlenen çalışma ağacı temiz.
- Backend `127.0.0.1:8000` (`/api/v1/health` → `ok`, sürüm `2.0.0`), frontend `127.0.0.1:5173` çalışıyor.
- SQLite `data/database/tezlify_studio.db`, `PRAGMA integrity_check` → `ok`.
- Scheduler çalışmıyor (`is_running:false`).
- Tek aktif bağlantı: `103d53ec-61da-4fa7-b0f7-96955ab8314c`, 7 scope, iki kanal:
  - `Resilience Channel` (`5d26da930c7ee0ffc9556f9894080483`) — devre dışı
  - `İsa Tezcan` (`d1bb27b003dd41ea91227107e2df730d`) — etkin ve seçili
- Keychain: `TezlifyStudio_access` ve `TezlifyStudio_refresh` öğeleri aktif bağlantı referansı için **mevcut**.

---

## 4. Analytics API Aktivasyonu ve Gerçek Veri

### 4.1 Canlı ölçüm

Ölçüm zamanı: **2026-11-05T20:44:13Z**

| Aralık | `available` | `reason` | `source` | Tarih aralığı |
|---|---|---|---|---|
| 7 gün | `false` | `api_not_enabled` | `null` | 2026-10-30 → 2026-11-05 |
| 28 gün | `false` | `api_not_enabled` | `null` | 2026-10-09 → 2026-11-05 |

Dönen açıklama aynen: *"YouTube Analytics API bu Google Cloud projesinde etkin değil. Google Cloud Console üzerinden API'yi etkinleştirmeniz gerekir."*

### 4.2 UI doğrulaması

- Genel Panel: "28 GÜN GÖRÜNTÜLEME" kartı `Kullanılamıyor` + `YouTube Analytics API kapalı` etiketi; gövdede aynı açıklama.
- Analitik sayfası: "YouTube Analytics verisi kullanılamıyor" başlığı, aynı açıklama ve "Bağlı Hesaplar" yönlendirmesi.
- Hiçbir yerde sıfır/uydurma Analytics değeri gösterilmiyor; `formatNumber` bilinmeyen değerlerde `—` üretiyor.

### 4.3 Sonuç ve kullanıcı aksiyonu

Analytics API bu Google Cloud projesinde etkin olmadığı için **gerçek Analytics kabulü yapılamadı**. Sahte veri üretilmedi, API etkinmiş gibi işlem yapılmadı.

**Gerekli kullanıcı işlemi:**
1. OAuth istemcisinin bağlı olduğu Google Cloud projesini açın.
2. **APIs & Services → Library → "YouTube Analytics API"** → **Enable**.
3. (Gelir verisi istenecekse) **"YouTube Analytics API"** yanında **monetary** kapsamının onaylı olduğundan emin olun; gelir için ayrıca yeniden yetkilendirme gerekir.
4. Google tarafında etkinleşmenin yayılması için birkaç dakika bekleyip uygulamada **Yenile** deyin.
5. Uygulama yeniden başlatılacaksa bunu kullanıcı onayıyla yapın; mevcut token geçerliliği bundan etkilenmez.

Bu adımlar tamamlanana kadar Analytics maddesi **BLOCKED** kalır.

---

## 5. Çoklu Hesap ve Çoklu Kanal

### 5.1 Gerçek durum

- Tek gerçek Google hesabı bağlı. İkinci Google hesabı mevcut değil; sahte hesapla gerçek kabul yapılmadı.
- Aynı hesap altında **iki kanal** keşfedilmiş durumda (yukarıdaki liste); biri devre dışı, biri etkin/seçili. Bu, tek hesapla çoklu kanal izolasyonunun gerçek veriyle var olduğunu gösterir, ancak **çoklu hesap** kabulünü kanıtlamaz.
- "Hesap Ekle" / yeniden bağlanma giriş noktaları ve bunların `intent=add_account|reconnect` + `connection_id` sözleşmesi mevcut; bu akışın uçtan uca gerçek kabulü ikinci Google hesabı gerektirir.

### 5.2 Testlerle doğrulanan izolasyon sözleşmesi

Mock HTTP ve sahte portlarla doğrulananlar (gerçek API kabulü değildir):

- Her istek tek bağlantı token'ı ve tek `external_channel_id` ile bağlanıyor; `mine=true` / `channel==MINE` kullanılmıyor.
- Token referansı kanal değil bağlantı bazlı.
- İki hesap iki bağlantı olarak ayrışıyor; kanal seçimi değiştiğinde önceki kanalın durumu yeniden kullanılmıyor.
- Yeniden keşif, eski bağlantıyı silmeden güncelliyor; bağlantı kesilmeden kanal devre dışı bırakılabiliyor.

**Sonuç:** `PASS_WITH_NOTES`. Gerçek ikinci hesapla kabul için kullanıcı aksiyonu gerekiyor:

1. İkinci bir Google hesabıyla **Bağlı Hesaplar → Hesap Ekle** akışını tamamlayın.
2. İki hesabın kanallarının global seçicide ayrı listelendiğini, seçim değişince Dashboard/Analitik/Yorumlar verilerinin hesap sınırında kaldığını doğrulayın.
3. Bu tamamlanana kadar çoklu hesap gerçek kabulü açık kalır.

---

## 6. OAuth Yetki Sertleştirmesi

### 6.1 Yetenek → scope eşlemesi (Google dokümantasyonuna göre)

| Yetenek | Gereken scope | Durum |
|---|---|---|
| Kimlik / e-posta / profil | `openid`, `userinfo.email`, `userinfo.profile` | Varsayılan |
| Kanal, video, playlist okuma | `youtube.readonly` | Varsayılan |
| Analytics raporları | `yt-analytics.readonly` | Varsayılan |
| Video yükleme | `youtube.upload` | Varsayılan |
| Yorum okuma/yanıtlama/moderasyon | `youtube.force-ssl` | Varsayılan |
| Gelir (estimatedRevenue) | `yt-analytics-monetary.readonly` | **Opsiyonel**, varsayılan değil |

Geniş `https://www.googleapis.com/auth/youtube` scope'u kullanılmıyor.

### 6.2 Yapılan değişiklikler

1. **Yetenek grupları:** `SCOPE_IDENTITY`, `SCOPE_CHANNEL_READ`, `SCOPE_ANALYTICS`, `SCOPE_UPLOAD`, `SCOPE_COMMENTS` ve `SCOPE_CAPABILITIES` tanımlandı. `YOUTUBE_SCOPES` bu grupların birleşimi; içerik ve kapsam **değişmedi**.
2. **Gelir scope'u:** `SCOPE_REVENUE` / `OPTIONAL_SCOPES` olarak ayrıldı; varsayılan onaya eklenmedi. Böylece gereksiz geniş onay istenmiyor.
3. **Artımlı yetkilendirme:** Auth URL'ye `include_granted_scopes=true` eklendi. Google, yeni onayda önceki izinlerle birleşim döndürür; mevcut token'lar etkilenmez ve gelecekteki kısmi onay akışı için zemin hazırlanır.
4. **Analytics hata metinleri:** `forbidden` ve `api_error` nedenleri için Türkçe açıklama eklendi; Dashboard etiketleri genişletildi.

### 6.3 Neden varsayılan onay daraltılmadı?

Upload ve yorum yetenekleri ana UI'dan erişilebilir durumda. İlk onayda yalnızca okuma istemek, kullanıcı "Video Yükle" veya "Yorumlar"a girdiğinde eksik scope ile başarısız olur ve UI'da yeniden onay akışı henüz yok. Bu nedenle:

- Mevcut davranış korunarak yalnızca yapısal ayrım ve `include_granted_scopes` eklendi.
- Daraltma, aşağıdaki geçiş planı tamamlanınca yapılmalı.

### 6.4 Güvenli geçiş planı (uygulanmadı, öneri)

1. **Faz A (bu commit):** Yetenek grupları + `include_granted_scopes=true`. Token geçersizliği yok. ✅
2. **Faz B:** UI'da yetenek bazlı yeniden onay çağrıları (ör. yükleme ekranında "Yükleme izni ver"). `generate_auth_url`'e isteğe bağlı `capabilities` parametresi eklenir; varsayılan tüm yetenekler kalır.
3. **Faz C:** Yeni bağlantılarda ilk onay yalnızca `identity + channel_read`; analitik/yükleme/yorum ihtiyaç anında artımlı istenir. `granted_scopes_json` üzerinden yetenek durumu UI'da gösterilir.
4. **Faz D:** Eski bağlantılar için yeniden onay istemek yerine mevcut 7 scope korunur; kullanıcı yalnızca yeni hesap eklerken daraltılmış akışı görür. Böylece mevcut token'lar geçersiz kılınmaz.
5. Her fazda gerçek OAuth kabulü kullanıcı onayıyla, ayrı bir oturumda yapılır.

**Sonuç:** `PASS` (yapısal sertleştirme ve güvenli geçiş planı tamam). Gerçek yeni onay akışı bu stage'de tetiklenmedi.

---

## 7. Dashboard / Video Listesi Veri Tutarsızlığı

### 7.1 Kanıt

Ölçüm zamanı: **2026-11-05T20:44:25Z**

| Kaynak | Değer |
|---|---|
| `channels.list` → `statistics.videoCount` | `0` |
| `channels.list` → `statistics.viewCount` | `0` |
| uploads playlist (`playlistItems`) → `pageInfo.totalResults` | `2` |
| `videos.list` ile dönen öğe | `1` (`1DMEIRsLUD0`, gizlilik `private`) |

**Açıklama:** YouTube `videoCount` yalnızca **herkese açık** videoları sayar. Uploads playlist'i sahibin özel/liste dışı videolarını da içerir. Gerçek kanalda herkese açık video olmadığı için `0` doğrudur; liste tarafında özel bir video görünmesi tutarsızlık değildir. Playlist `totalResults=2` iken `videos.list`'in 1 öğe döndürmesi, ikinci girdinin o anda çözümlenemeyen/silinmiş bir kayda işaret ettiğini gösterir; yazma işlemi yapılmadı, yalnızca gözlem kaydedildi.

### 7.2 Yapılan iyileştirme

- `ChannelOverviewPage`: "Video sayısı" kartına **"Yalnızca herkese açık videolar"** alt açıklaması eklendi.
- `YouTubeVideosPage`: listenin **özel ve liste dışı** videoları da içerdiği, kanal kartındaki sayının yalnızca herkese açık videoları saydığı belirtildi.
- `backend/tests/integration/test_real_youtube_stage63.py`: `videoCount=0` ile `totalResults=2` ve özel video dönüşünü birlikte doğrulayan sözleşme testi eklendi.
- Canlı UI'da her iki metin de doğrulandı (Kanal Özeti ve Videolar sayfaları).

---

## 8. Legacy Kayıtlar ve Keychain Denetimi

### 8.1 Legacy publish kayıtları

Ölçüm zamanı: **2026-11-05T20:45:26Z** (salt okunur)

- Toplam **135** kayıt.
- Tümü `channel_attribution = legacy_single_account`.
- Tümü `channel_id = 5d26da930c7ee0ffc9556f9894080483` → **Resilience Channel** (devre dışı test kanalı), gerçek "İsa Tezcan" kanalı değil.
- Durum dağılımı: 54 `paused`, 27 `cancelled`, 27 `failed`, 27 `published`.
- Yalnızca 1 farklı dolu `external_video_id`: `mock_yt_vid_42`; diğerleri `NULL`. Gerçek 11 karakterli YouTube video ID'si yok.
- Başlıklar: "Zombie Upload", "Session Expired Test", "My Awesome YouTube Animation", "Job to Cancel", "First Publish" (her biri 27).

**Sonuç:** 135 kaydın gerçek kanala ait olduğuna dair kanıt yok; aksine, tamamı test/legacy verisi ve devre dışı test kanalına bağlı. Gerçek kanala atama yapılmadı.

### 8.2 Keychain

- `TezlifyStudio_access` / `103d53ec-...` → **PRESENT**
- `TezlifyStudio_refresh` / `103d53ec-...` → **PRESENT**
- Hiçbir öğe okunmadı, yazılmadı, kopyalanmadı veya silinmedi.

### 8.3 Güvenli temizlik önerisi (uygulanmadı, ayrı onay gerekir)

1. Önce DB ve Keychain için ayrı yedek alın (mevcut `data/database/backups/` kullanılabilir).
2. Legacy 135 kaydı silmek yerine arşiv tablosuna taşıma veya `status = archived` ile işaretleme önerilir; geri alınabilirlik korunur.
3. Keychain öğeleri yalnızca bağlantı gerçekten kaldırılacaksa ve kullanıcı açıkça onaylarsa silinmeli; "orphan" görünen öğeler bile önce envanterlenmeli.
4. Temizlik, ayrı bir stage/onay kapsamında ve yedek doğrulandıktan sonra yapılmalı.

---

## 9. Test ve Doğrulama

### 9.1 Otomatik testler (mock / sözleşme)

| Komut | Sonuç |
|---|---|
| `.venv/bin/python -m pytest backend/tests/integration/test_real_youtube_stage63.py -q` | **7 passed** |
| `.venv/bin/python -m pytest backend/tests -q` (tam suite) | **158 passed**, 1 deprecation warning |
| `npm test -- --run` (frontend) | **4 passed** |
| `npx tsc --noEmit` (frontend) | Hatasız |

Yeni kapsanan sözleşmeler:

- Varsayılan onay = yetenek gruplarının birleşimi; geniş `auth/youtube` yok.
- Gelir scope'u varsayılan onayda değil, opsiyonel.
- Auth URL `include_granted_scopes=true` içeriyor ve scope listesi `YOUTUBE_SCOPES` ile aynı.
- `forbidden` ve `api_error` Analytics nedenleri anlamlı Türkçe açıklama üretiyor; bilinmeyen neden genel metne düşüyor.
- `videoCount=0` iken uploads listesinin 2, `videos.list`'in 1 özel video döndürmesi birlikte doğrulanıyor.

Bu testler **gerçek API kabulü değildir**; gerçek ortam ölçümleri Bölüm 4–8'de ayrıca verilmiştir.

### 9.2 Gerçek ortam doğrulaması

- Canlı backend `/api/v1/channels/youtube/analytics` 7 ve 28 gün: `api_not_enabled` (Bölüm 4).
- Canlı `/api/v1/social/youtube/status`: 1 aktif bağlantı, 7 scope, 2 kanal (Bölüm 3).
- Canlı `/api/v1/channels/youtube/overview`: `video_count=0`; `/videos`: `total_results=2`, dönen 1 özel video (Bölüm 7).
- Canlı UI: Dashboard Analytics uyarısı, Kanal Özeti video sayısı açıklaması, Videolar liste açıklaması ve Analitik sayfası doğrulandı.

**Not:** Çalışan backend süreci kod değişikliklerinden önce başlatıldığı için yeni `forbidden`/`api_error` metinleri ve `include_granted_scopes` canlı süreçte henüz yüklü değil; bunlar testlerle doğrulandı. Analytics API durumu sunucu tarafında değişmediğinden canlı Analytics ölçümü geçerlidir. Backend yeniden başlatma kullanıcı onayı gerektirir ve bu stage'de yapılmadı.

---

## 10. Değiştirilen Dosyalar

- `backend/src/tezlify_studio/infrastructure/youtube/youtube_creator_api.py` — yetenek bazlı scope sabitleri, gelir scope'unun opsiyonel ayrılması.
- `backend/src/tezlify_studio/infrastructure/media/youtube_api_client_impl.py` — `include_granted_scopes=true`.
- `backend/src/tezlify_studio/application/use_cases/get_channel_analytics_use_case.py` — `forbidden` ve `api_error` açıklamaları.
- `frontend/src/pages/DashboardPage.tsx` — yeni Analytics neden etiketleri ve detayları.
- `frontend/src/pages/ChannelOverviewPage.tsx` — video sayısının yalnızca herkese açık videoları saydığı notu.
- `frontend/src/pages/YouTubeVideosPage.tsx` — listenin özel/liste dışı videoları içerdiği notu.
- `backend/tests/integration/test_real_youtube_stage63.py` — yeni sözleşme testleri.

---

## 11. Riskler ve Açık Noktalar

1. **Analytics gerçek kabulü yok:** API etkinleştirilmeden gerçek metrik, tarih aralığı veya gelir doğrulanamaz.
2. **İkinci Google hesabı yok:** Çoklu hesap izolasyonu yalnızca sözleşme testleriyle kanıtlı; gerçek eşzamanlı iki hesapla kabul açık.
3. **Varsayılan onay hâlâ geniş:** Yedi scope ilk onayda isteniyor. Daraltma, UI yeniden onay akışı gerektirdiği için bilinçli olarak ertelendi.
4. **Gelir verisi:** `yt-analytics-monetary.readonly` varsayılan değil; gelir kutusu işaretlense bile mevcut token'da bu scope olmadığı için `available=false` dönecek. Bu davranış veri uydurmuyor, açıklama üretiyor.
5. **Playlist `totalResults=2` / `videos.list=1`:** İkinci girdinin nedeni (silinmiş/çözümlenemeyen kayıt) yazma yapılmadan kesinleştirilemez; kullanıcıya yanlış sayı gösterilmemesi için UI açıklaması eklendi.

---

## 12. Kullanıcıdan Gereken Aksiyonlar

1. **Analytics (zorunlu):** Google Cloud Console → Library → **YouTube Analytics API** → Enable. Ardından uygulamada Yenile.
2. **Gelir verisi (opsiyonel):** Monetary Analytics kapsamı için yeniden yetkilendirme onayı.
3. **Çoklu hesap (opsiyonel):** İkinci Google hesabıyla "Hesap Ekle" akışını tamamlayıp izolasyonu doğrulama.
4. **Backend yeniden başlatma (opsiyonel):** Yeni hata metinlerinin canlı süreçte görünmesi için; onay gerektirir.
5. **Temizlik (opsiyonel):** Legacy 135 kayıt ve Keychain öğeleri için ayrı onaylı temizlik planı.

---

## 13. Çalışma Ağacı ve Commit Durumu

- Stage 6.3 kod ve test değişiklikleri yerel commit'lere alındı.
- Nihai commit mesajı: `test(studio): verify analytics and multi-account hardening`.
- Push veya deployment yapılmadı.
- Çalışma ağacında kalan izlenmeyen dosyalar önceki stage'lere ait rapor/kanıt dosyalarıdır; bu stage kapsamında silinmedi.

---

## 14. Nihai Karar

**`PASS_WITH_NOTES`**

- Analytics aktivasyonu ve gerçek Analytics verisi: **BLOCKED** (kullanıcı Google Cloud Console'da API'yi etkinleştirmeli).
- Çoklu hesap gerçek kabulü: **PASS_WITH_NOTES** (ikinci Google hesabı yok; çoklu kanal gerçek veriyle doğrulandı, izolasyon sözleşmesi testlerle kanıtlı).
- OAuth sertleştirmesi, veri tutarsızlığı açıklaması, legacy/Keychain denetimi: **PASS**.

Gerçek ortamda doğrulanmayan maddelere PASS verilmedi; hiçbir yıkıcı işlem, token işlemi veya push/deploy yapılmadı.
