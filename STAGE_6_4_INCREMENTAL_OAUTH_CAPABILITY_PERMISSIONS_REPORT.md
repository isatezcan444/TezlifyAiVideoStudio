# Stage 6.4 — Incremental OAuth ve Yetenek Bazlı İzinler Raporu

Tarih: 2026-11-06
Tip: KODLAMA + doğrulama
Karar: **PASS_WITH_NOTES**

Bu aşamada gerçek Google OAuth onayı başlatılmadı, gerçek kanalda yükleme/yorum/moderasyon/metadata değişikliği yapılmadı, token yenilenmedi, Keychain kaydı oluşturulmadı veya değiştirilmedi. Tüm OAuth ve yetenek testleri fake portlarla yapıldı; bu sonuçlar gerçek Google kabulü sayılmaz.

## 1. Başlangıç ve bitiş durumu

| Alan | Değer |
| --- | --- |
| Repository | `/Users/isatezcan/Documents/Github/Tezlify-AI-Video-Studio` |
| Başlangıç SHA | `3686b24` (`test(studio): verify analytics and multi-account hardening`) |
| Kod commit'leri | `bf5c9b9` (`feat(studio): request youtube oauth scopes incrementally`), `d8926de` (`feat(studio): enforce youtube capabilities per connection`), `571d860` (`feat(studio): show youtube capability permissions in ui`) |
| Son doğrulama commit'i | `test(studio): verify incremental oauth capabilities` |
| Mevcut gerçek bağlantı | `103d53ec-61da-4fa7-b0f7-96955ab8314c` / `active` / 7 scope |
| Veritabanı | Değişmedi (aşağıda kanıt) |
| Keychain | Değişmedi (aşağıda kanıt) |
| Migration | Gerekmiyor; şema değişmedi, yetenekler mevcut `granted_scopes_json` üzerinden türetiliyor |
| Push / deploy | Yapılmadı |

## 2. Önce / sonra scope karşılaştırması

### Stage 6.3 (önce)

`YOUTUBE_SCOPES` / varsayılan onay:

1. `openid`
2. `https://www.googleapis.com/auth/userinfo.email`
3. `https://www.googleapis.com/auth/userinfo.profile`
4. `https://www.googleapis.com/auth/youtube.readonly`
5. `https://www.googleapis.com/auth/yt-analytics.readonly`
6. `https://www.googleapis.com/auth/youtube.upload`
7. `https://www.googleapis.com/auth/youtube.force-ssl`

`yt-analytics-monetary.readonly` isteğe bağlıydı, varsayılan onayda yoktu.

### Stage 6.4 (sonra)

- **Yeni bağlantı varsayılanı yalnızca temel grant (4 scope):** `openid`, `userinfo.email`, `userinfo.profile`, `youtube.readonly`.
- `analytics` → `yt-analytics.readonly` yalnızca Analytics kullanıldığında.
- `upload` → `youtube.upload` yalnızca yükleme kullanıldığında.
- `comments` → `youtube.force-ssl` yalnızca yorum yazma/moderasyon kullanıldığında.
- `revenue` → `yt-analytics-monetary.readonly` isteğe bağlı, hiçbir varsayılan onaya dahil değil.

Kaynak: `backend/src/tezlify_studio/domain/value_objects/youtube_capabilities.py` — `BASE_CAPABILITIES`, `CAPABILITY_SCOPE_MAP`, `OPTIONAL_CAPABILITIES`.

### Mevcut gerçek bağlantı

Mevcut bağlantı zaten 7 scope içeriyor. Stage 6.4 hiçbir noktada scope daraltmıyor:

- `generate_auth_url` reconnect akışında mevcut scope'ların yeteneklerini istenenlerle birleştirir (`existing_capabilities + requested`).
- `complete_youtube_authentication` mevcut bağlantıda Google'ın döndürdüğü scope'ları eski scope'larla birleştirir (`merge_capability_scopes`).
- Sonuç: mevcut bağlantı için yeniden onay istenmedi ve tüm temel yetenekler `active` görünüyor.

## 3. Yetenek mimarisi

Tek kaynak: `domain/value_objects/youtube_capabilities.py`

- Yetenekler: `identity`, `channel_read`, `analytics`, `upload`, `comments`, `revenue`.
- Fonksiyonlar: `normalize_capabilities` (whitelist, bilinmeyeni reddeder), `capabilities_for_scopes`, `has_capability`, `scopes_for_capabilities` (temel grant her zaman dahil), `missing_capabilities`, `merge_capability_scopes`.

Merkezi karar noktası: `application/services/youtube_capability_service.py`

- `resolve(connection)` → her yetenek için `active`, `scope_required`, `api_not_enabled`, `reauth_required`, `unavailable`.
- `can(connection, capability)` ve `require(connection, capability)`.
- Yalnızca bağlantının kendi `granted_scopes` değerini okur; iki hesap arasında sızma yok.
- `api_not_enabled` ayrı bir durumdur: scope verilmiş olsa bile Analytics çağrısı yapılmaz ve kullanıcıya Google Cloud yönlendirmesi gösterilir.

Uygulama kapıları:

- Yükleme: `publish_video_to_youtube_use_case` ve `resume_youtube_upload_use_case` → `require(upload)`.
- Yorum yazma/moderasyon: `reply_to_comment_use_case`, `set_comment_moderation_use_case` → `require(comments)`.
- Analytics: `get_channel_analytics_use_case` → scope yoksa Google'a hiç gitmeden `insufficient_scope`; API kapalıysa `api_not_enabled`.
- Gateway: `YouTubeCreatorGateway.bind` → `require(channel_read)`.
- API hataları: 403 gövdesine `capability` eklenir (`presentation/api/app.py`).

API yüzeyi:

- `GET /api/v1/social/connections` → her bağlantıda `capabilities`.
- `GET /api/v1/social/connections/{id}/capabilities`.
- `POST /api/v1/social/connections/{id}/grant` → yalnızca gerçekten eksik yetenekler için artımlı onay URL'i üretir (mevcutlar korunur).
- `POST /api/v1/social/youtube/connect?capabilities=analytics,upload` → ek yetenekler.

## 4. OAuth güvenlik değerlendirmesi

Korunanlar:

- PKCE S256 (`code_challenge_method=S256`) her oturumda üretiliyor.
- `state` tek kullanımlık; tekrar kullanım `DuplicateOAuthCallbackException` fırlatır.
- Oturum TTL'i 10 dakika; süresi geçen state reddedilir.
- `connection_id` ve istenen yetenekler oturuma bağlanıyor; callback yalnızca aynı bağlantıyı güncelliyor.
- `include_granted_scopes=true`, `access_type=offline`, `prompt=consent` korunuyor.
- Google'ın döndürdüğü `scope` otorite kabul edilir; istenen = verilen varsayılmaz.
- Yenileme tokenı yoksa mevcut Keychain değeri kullanılır; boş değerle üzerine yazılmaz. Token yoksa bağlantı kaydedilmeden hata verilir.
- Başarısız/iptal edilen artımlı onayda veritabanı ve Keychain dokunulmaz.
- Frontend'e token veya Keychain referansı gönderilmiyor; yalnızca scope adları ve yetenek durumları gideriliyor.

Canlı doğrulama (gerçek istek, onay yok):

- Bilinmeyen yetenek ile `POST /grant` → `400 VALIDATION_ERROR` (`Bilinmeyen yetenek: admin`); oturum oluşmadı.

## 5. Mevcut bağlantı ve token koruma kanıtı

Başlangıç ve bitişte aynı satır (read-only sorgu):

```
103d53ec-61da-4fa7-b0f7-96955ab8314c | active | token_reference=103d53ec-...8314c
scopes = [userinfo.email, youtube.upload, youtube.force-ssl, openid,
          yt-analytics.readonly, youtube.readonly, userinfo.profile]
updated_at = 2026-11-05 20:15:46.728320
```

- Keychain varlık kontrolü (değer okunmadan): `TezlifyStudio_refresh` ve `TezlifyStudio_access` için `security find-generic-password` çıkış kodu `0`. Token değerleri görüntülenmedi.
- Canlı API: `GET /connections` artık `capabilities` döndürüyor; mevcut bağlantıda `identity`, `channel_read`, `upload`, `comments` **active**, `analytics` **api_not_enabled** (scope var), `revenue` **scope_required** (isteğe bağlı).
- Bu, mevcut bağlantının yeniden onay istemeden çalışmaya devam ettiğini gösterir; yalnızca gerçekten eksik olan `revenue` için buton sunulur.

## 6. Frontend akışları

- **Bağlı Hesaplar:** her bağlantı için yetenek ızgarası ve durum etiketi (`aktif`, `izin gerekli`, `API kapalı`, `yeniden bağlan`, `kullanılamıyor`). `scope_required` için artımlı onay butonu; `api_not_enabled` için Google Cloud Console metni, buton yok.
- **Video Yükle:** `upload` aktif değilse yükleme girişi gizlenir ve neden + "YouTube yükleme izni ver" gösterilir; izin sonrası kanal seçimi korunarak sayfa yenilenir; hâlâ yoksa engellenir.
- **Analitik:** `insufficient_scope` → izin butonu; `api_not_enabled` → Google Cloud yönlendirmesi, buton yok; veri yoksa boş durum korunur.
- **Yorumlar:** okuma çalışmaya devam eder; yanıt/moderasyon butonları izin yokken devre dışı, "Yorum yönetimi izni ver" sunulur ve hiçbir yazma çağrısı yapılmaz.
- **Dönüş davranışı:** loopback callback sayfası `postMessage` ile aynı sekmeye başarı/başarısızlık bildirir; sayfa terk edilmez, kanal seçimi (`tezlify.active_channel_id`) korunur.

Canlı UI doğrulaması (gerçek backend + gerçek veritabanı, yalnızca okuma):

- Bağlı Hesaplar: "Kanal okuma / Analytics / Video yükleme / Yorum yönetimi = aktif", "Gelir verisi = izin gerekli" + "Gelir izni ekle".
- Video Yükle: mevcut bağlantı için yükleme girişi görünür (izin engeli yok).
- Analitik: "YouTube Analytics API etkin değil" + Google Cloud Console metni; izin butonu yok; durum etiketi `api_not_enabled`.
- Yorumlar: yorum listesi okunuyor, izin banner'ı yok.

## 7. Test sonuçları

| Paket | Sonuç |
| --- | --- |
| Backend tam suite | **188 passed** |
| Frontend tam suite | **18 passed** (3 dosya) |
| Yeni Stage 6.4 backend testleri | **29 passed** (`backend/tests/integration/test_incremental_oauth_stage64.py`) |
| Yeni frontend testleri | **14 passed** (10 sayfa + 4 OAuth helper) |
| TypeScript `tsc --noEmit` | Temiz |

Backend kapsamı: temel scope seti, yetenek→scope eşlemesi, bilinmeyen yetenek reddi, analytics/upload/comments izin var/yok, revenue opsiyonel, Google'ın daha az scope döndürmesi, yenileme tokenı içermeyen yanıt, mevcut grant'lerin korunması, state tek kullanım, başarısız artımlı onayın bağlantıyı bozmaması, iki bağlantı arasında yetenek izolasyonu, `api_not_enabled` ile `scope_required` ayrımı.

Frontend kapsamı: yetenek durumlarının render edilmesi, upload/analytics/comments izin ekranları, izin butonlarının doğru yeteneği istemesi, iptalde bağlantının korunduğu mesajı, kanal seçiminin korunması, `postMessage` başarı/başarısızlık davranışı.

**Not:** Tüm bu testler fake portlar ve mock'lu API kullanır. Gerçek Google OAuth kabulü değildir.

## 8. Gerçek ortamda doğrulanamayan noktalar

1. Gerçek artımlı OAuth onay turu (kullanıcı onayı olmadan başlatılmadı).
2. Google'ın gerçekten daha az scope döndürmesi veya kullanıcının reddetmesi.
3. Yeni bir gerçek Google hesabıyla ikinci bağlantı (hesap hâlâ yok).
4. Artımlı onay sırasında gerçek Keychain yazımı/yenileme tokenı davranışı (işlem yapılmadı).
5. YouTube Analytics API'nin gerçekten etkinleştirilmesi — **hâlâ kapalı**; Stage 6.3'teki `api_not_enabled` durumu çözülmüş sayılmaz.
6. Yeni bağlantının Google'a yalnızca 4 temel scope ile gittiğinin canlı doğrulanması (canlı OAuth başlatılmadı; birim testte doğrulandı).

## 9. Açık riskler

- Analytics `api_not_enabled` durumu süreç içi bellekte tutulur; backend yeniden başlarsa ilk Analytics çağrısına kadar durum bilinmez, sonra yeniden işaretlenir.
- Yetenekler bağlantı kapsamlıdır: aynı Google hesabındaki tüm kanallar aynı grant'i paylaşır (istenen model).
- Yorum okuma `channel_read` ile çalışır; yazma yalnızca `comments` ile. Bu ayrım UI'da ve resolver'da uygulanıyor, ancak gerçek API'nin 403 davranışı canlı test edilmedi.
- `revenue` onayı verilse bile Analytics API kapalı olduğu için gerçek gelir verisi alınamaz.
- Gerçek ortamda artımlı onayın `prompt=consent` nedeniyle ekran göstermesi beklenir; bu davranış canlı doğrulanmadı.
- Geliştirme backend'i yeni kod için yeniden başlatıldı (yerel süreç); veritabanı ve Keychain'e yazılmadı.

## 10. Sonuç

Artımlı yetenek modeli, merkezi yetenek çözücü, backend kapıları, API uçları ve frontend izin ekranları uygulandı; mevcut 7-scope bağlantı ve Keychain token'ları değişmeden çalışmaya devam ediyor. Gerçek Google onayı, ikinci hesap ve Analytics API aktivasyonu bu aşamada doğrulanmadı.

**PASS_WITH_NOTES**
