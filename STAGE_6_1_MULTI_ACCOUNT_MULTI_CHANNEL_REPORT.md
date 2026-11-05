# TEZLIFY CREATOR STUDIO
## STAGE 6.1 — MULTI-ACCOUNT & MULTI-CHANNEL MANAGEMENT ARCHITECTURE REPORT

**Tarih:** 5 Kasım 2026
**Başlangıç SHA:** `f66924063a8f185f8d4247ddb004a1b924760517` — `feat(studio): pivot to youtube creator management`
**Bitiş SHA:** Bu raporun yer aldığı son yerel commit — `feat(studio): support multiple platform accounts and youtube channels` (hash: `git log -1 --format=%H`)
**Kapsam:** Ürünün tek YouTube hesabına bağlı yapısının, platform → hesap → kanal ayrımına sahip çok hesaplı/çok kanallı mimariye taşınması; veri kaybı olmadan migration; OAuth/Keychain izolasyonu; kanal keşfi; global kanal seçici; kanal kapsamlı dashboard, upload, scheduler ve analytics.
**Ölçüm zamanı:** Aşağıdaki tüm canlı ölçümler 2026-11-05 18:25–18:31 (yerel, +03) aralığında alınmıştır.

---

## 1. Yönetici Özeti

- Ürün artık tek bir YouTube hesabına bağlı değil. Domain modeli **Platform → PlatformConnection → PlatformChannel → ChannelSelection** ayrımına taşındı.
- Birden fazla Google hesabı bağlanabilir; her hesabın altındaki birden fazla kanal ayrı kayıt olarak tutulur ve tek panelden yönetilir.
- Her bağlantının token'ı kendi `token_reference` değeri üzerinden macOS Keychain'den okunur; bir bağlantı diğerinin token'ını asla ödünç almaz.
- Mevcut tek YouTube bağlantısı ve 135 yayın kaydı **veri kaybı olmadan** yeni yapıya taşındı; eski `social_accounts` kaydının kimliği ve Keychain referansı korundu.
- Migration öncesi iki doğrulanmış SQLite yedeği alındı; migration sonrası eski↔yeni eşleşme, satır sayıları ve foreign key bütünlüğü doğrulandı.
- Global kanal seçici, hesap yöneticisi, global dashboard ve kanal kapsamlı dashboard/analytics/upload/scheduler akışları eklendi.
- Instagram ve TikTok yalnızca yetenek tanımı (capability descriptor) olarak mevcut; OAuth, API çağrısı, örnek veri veya sahte başarı yanıtı yok.
- Gerçek YouTube kanalına yazma işlemi yapılmadı. Tüm yazma akışları fake port / mock transport ile test edildi.

**Sonuç: PASS_WITH_NOTES** — Çok hesaplı/çok kanallı mimari, migration ve izolasyon testleri geçti. Canlı hesapta yazma doğrulaması ve Keychain durumu Bölüm 13'te not edilmiştir.

---

## 2. Başlangıç Durumu

| Alan | Değer |
|---|---|
| Repo | `/Users/isatezcan/Documents/Github/Tezlify-AI-Video-Studio` |
| Branch | `main` (yerel) |
| Başlangıç HEAD | `f669240` — `feat(studio): pivot to youtube creator management` |
| Başlangıç veritabanı revizyonu | `b71e29c04d1a` |
| Başlangıç verisi | 1 social account, 135 publish record, 324 media asset, 236 proje |
| Başlangıç test durumu | Backend 113 test, frontend 4 test (Stage 6.1 öncesi) |

Önceki aşamalardan kalan izlenmeyen `STAGE_5_*` raporları, `evidence/**` dosyaları ve `backend/uv.lock` Stage 6.1 commit'ine dahil edilmedi.

---

## 3. Stage 6.0 Denetimi: Gerçek Tek-Hesap Varsayımları

Stage 6.0'da `platforms`/`channels` portları platformdan bağımsız görünse de gerçekte tek hesap varsayımı korunuyordu:

1. **Tek sosyal hesap kaydı:** `social_accounts` tablosunda tek satır; hesap = kanal kabul ediliyordu.
2. **Tek kanal kimliği:** Dashboard, video, analytics, yorum ve upload akışları `get_account()` ile tek hesabı çözüyor; `channel_id` parametresi kullanıcıdan beklenmiyordu.
3. **Token referansı = hesap kimliği:** Keychain anahtarı `social_accounts.id` üzerinden üretiliyordu; ikinci hesap eklendiğinde ilk hesabın üzerine yazma riski vardı.
4. **Sabit kanal varsayımı:** YouTube adapter çağrılarında `mine=true` / `channel==MINE` gibi "oturumun tek kanalı" varsayımları ve tek `channel_id` alanı baskındı.
5. **Yayın kayıtlarında kanal yok:** `publish_records` yalnızca `social_account_id` taşıyordu; kanal ve bağlantı ayrımı yoktu.
6. **Scheduler tek hesap:** Zamanlanmış yayınlar `social_account_id` ile çalışıyor; hangi kanala gideceği ayrı bir alanla ifade edilmiyordu.
7. **UI tek hesap:** "YouTube bağlantısı" kartı tek hesabı temsil ediyor; global kanal seçici ve hesap yöneticisi yoktu.

Bu nedenle Stage 6.1 yalnızca "ikinci hesap ekle" ekranı değil, domain, persistence, OAuth, kullanım senaryoları, scheduler ve UI düzeyinde tam bir ayrıştırma yaptı.

---

## 4. Yeni Domain ve Veritabanı Tasarımı

### 4.1 Domain kavramları

| Kavram | Sorumluluk | Ana alanlar |
|---|---|---|
| **Platform** | Yetenekleri tanımlayan statik katalog | `id`, `display_name`, `implemented`, `capabilities` |
| **PlatformConnection** | Bir platformdaki hesap/izin bağlantısı | `platform`, `account_external_id`, `account_display_name`, `connection_status`, `token_reference`, `granted_scopes`, `token_expires_at` |
| **PlatformChannel** | Bir bağlantı altındaki gerçek kanal | `platform_connection_id`, `channel_external_id`, `channel_name`, `channel_handle`, `avatar_url`, `description`, `is_primary`, `is_enabled`, `subscriber_count`, `uploads_playlist_id` |
| **ChannelSelection** | Kullanıcının aktif kanal tercihi | `active_channel_id`, `default_platform` |
| **ChannelContext** | Çözümlenmiş kanal + bağlantı çifti | `channel`, `connection` |
| **ChannelAccess** | Token erişim sonucu | access token, yenileme gereksinimi |

Yeni dosyalar:

- `backend/src/tezlify_studio/domain/entities/platform_connection.py`
- `backend/src/tezlify_studio/domain/entities/platform_channel.py`
- `backend/src/tezlify_studio/domain/entities/channel_selection.py`
- `backend/src/tezlify_studio/domain/value_objects/channel_context.py`
- `backend/src/tezlify_studio/domain/value_objects/channel_access.py`
- `backend/src/tezlify_studio/domain/enums/connection_status.py`

Portlar: `PlatformConnectionRepositoryPort`, `PlatformChannelRepositoryPort`, `ChannelSelectionRepositoryPort`, `ChannelContextResolverPort`, `ChannelAccessProviderPort`, `CreatorGatewayPort`.

Servisler: `ChannelContextService` (kanal çözümleme), `ConnectionTokenProvider` (bağlantıya özel token).

### 4.2 Veritabanı şeması

**`platform_connections`**

- PK: `id` (`VARCHAR(64)`)
- `UNIQUE(token_reference)`
- `UNIQUE(platform, account_external_id)` — aynı hesabın tekrar eklenmesini engeller
- Index: `platform`, `account_external_id`, `connection_status`
- Token değeri **yok**; yalnızca `token_reference` ve `token_expires_at`.

**`platform_channels`**

- PK: `id`
- FK: `platform_connection_id → platform_connections.id ON DELETE CASCADE`
- `UNIQUE(platform_connection_id, channel_external_id)` — aynı kanalın aynı bağlantı altında tekrarını engeller
- Index: `platform_connection_id`, `platform`, `channel_external_id`
- Aynı harici kanal kimliğinin iki farklı bağlantı altında oluşması uygulama katmanında `ChannelBindingMismatchException` ile kontrollü biçimde engellenir.

**`user_channel_preferences`**

- Tek satır (`id='default'`), `active_channel_id`, `default_platform`.

**`publish_records` (eklenen alanlar)**

- `channel_id`, `platform_connection_id`, `channel_attribution`
- `channel_attribution` değerleri: `exact`, `legacy_single_account`, `legacy_social_account`, `unresolved`.
- Index: `channel_id`, `platform_connection_id`.

**`scheduled_publishes` (yeniden oluşturuldu)**

- `channel_id`, `platform_connection_id`, `channel_attribution` eklendi.
- `social_account_id` nullable yapıldı; eski kayıtlar korunarak taşındı.
- Yeni kayıtlar `channel_attribution='exact'` ile oluşturulur.

Yetkisiz/eksik kanal çözümlemesi:

- Bilinmeyen kanal → `ChannelNotFoundException`
- Devre dışı kanal → `ChannelDisabledException`
- Pasif bağlantı → `ConnectionInactiveException`
- Çözümleme sırası: açık `channel_id` → kalıcı seçim → ilk etkin kanal (seçim kalıcılaştırılır).

---

## 5. Migration ve Veri Koruma

### 5.1 Migration güvenliği

Migration: `backend/alembic/versions/d61a0c1f4b2e_add_multi_account_connections.py` (`down_revision = c92f45a1d7b0`).

- DDL öncesi **SQLite backup API** ile zaman damgalı yedek alınır.
- Yedek `PRAGMA integrity_check` ile doğrulanır; boş dosya tespit edilirse migration durur.
- Yedek dizini `TEZLIFY_MIGRATION_BACKUP_DIR` ile değiştirilebilir; varsayılan `data/database/backups/`.
- Var olan tablolar `inspect()` ile kontrol edilir; migration tekrar çalıştırılabilir (idempotent).
- Yeni tablolar ve kolonlar yalnızca yoksa oluşturulur.

### 5.2 Legacy eşleme

- `social_accounts.id` → `platform_connections.id` (kimlik korunur).
- `token_reference` = eski hesap kimliği; **mevcut Keychain kaydı aynen kullanılmaya devam eder**.
- `account_external_id` = `legacy:{channel_id}`; gerçek Google kimliği ilk yeniden OAuth'ta güncellenir.
- Tek primary `platform_channels` kaydı oluşturulur (`metadata_json = {"migrated_from": "social_accounts"}`).
- Kullanıcının mevcut kanalı `user_channel_preferences.active_channel_id` olarak korunur.

### 5.3 Yayın kaydı eşleme

- Yalnızca **tam olarak 1 YouTube sosyal hesabı** varsa kayıtlar `legacy_single_account` olarak işaretlenir ve o kanala/bağlantıya bağlanır.
- Birden fazla hesap varsa tahmin yapılmaz; `channel_attribution='unresolved'`, `channel_id=NULL` olarak korunur.
- Zamanlanmış yayınlarda `social_account_id` güvenilir biçimde bir bağlantıya çözülebiliyorsa `legacy_social_account` atanır.
- Migration sonunda satır sayıları ve orphan kayıtlar doğrulanır; verify adımı başarısız olursa migration hata verir.

### 5.4 Gerçek veritabanı doğrulaması (ölçüm: 2026-11-05 18:25–18:27)

| Kontrol | Sonuç |
|---|---|
| Alembic revizyonu | `d61a0c1f4b2e` |
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
| `platform_channels` | 1 |
| `user_channel_preferences` | 1 |
| Bağlantı kimliği | `103d53ec-61da-4fa7-b0f7-96955ab8314c` |
| `token_reference` | `103d53ec-61da-4fa7-b0f7-96955ab8314c` (korundu) |
| Harici kanal | `UC_RESILIENCE` |
| Kanal kimliği | `5d26da930c7ee0ffc9556f9894080483` |
| Aktif seçim | `5d26da930c7ee0ffc9556f9894080483` |
| Yayın eşlemesi | 135 kayıt → `legacy_single_account`, 1 kanal, 1 bağlantı |
| `PRAGMA foreign_key_check` | Boş (ihlal yok) |
| Düz metin token kolonu | Yok (`token_reference` ve `token_expires_at` dışında token/secret kolonu yok) |

### 5.5 Yedekler

| Dosya | Revizyon | `integrity_check` | publish / account / media / project |
|---|---|---|---|
| `tezlify_studio_backup_20261105T152520Z.db` | `b71e29c04d1a` | `ok` | 135 / 1 / 324 / 236 |
| `tezlify_studio_pre_stage6_1_20261105T152524Z.db` | `c92f45a1d7b0` | `ok` | 135 / 1 / 324 / 236 |

Her iki yedek de Stage 6.1 öncesi durumu temsil eder; migration sonrası ana veritabanıyla satır sayıları eşleşmektedir.

---

## 6. Multi-Account OAuth ve Keychain İzolasyonu

### 6.1 OAuth akışı

- Her bağlama isteği kendi `state` ve PKCE `code_verifier` çiftini üretir (`OAuthSessionStore`).
- `state` tek kullanımlıktır; tekrar kullanım `DuplicateOAuthCallbackException` ile reddedilir.
- Callback, oturumdaki `code_verifier` ve `redirect_uri` ile token değişimi yapar.
- Kimlik çözümleme sırası: OIDC `sub` → e-posta → ilk kanal kimliği.
- Aynı Google hesabı tekrar bağlanırsa mevcut `PlatformConnection` güncellenir; ikinci kayıt oluşturulmaz.
- Farklı hesap, mevcut bir bağlantının kanalına sahipse `ChannelBindingMismatchException` ile reddedilir.
- Yeniden bağlama (`reconnect`) yalnızca hedef bağlantıyı günceller; diğer bağlantılara dokunmaz.

### 6.2 Keychain anahtarları

- Yeni bağlantılar: `token_reference = youtube.connection.<connection_id>`.
- Legacy bağlantı: eski `social_accounts.id` referansı korunur.
- Keychain servis adları değişmedi: `TezlifyStudio_access`, `TezlifyStudio_refresh`.
- `ConnectionTokenProvider` yalnızca çözümlenen `ChannelContext`'in `token_reference` değerini okur.
- Access token süresi dolduğunda yalnızca o bağlantının refresh token'ı kullanılır; refresh token yoksa `require_reauth()` döner ve başka grant'e geçilmez.
- Token değerleri hiçbir log satırına yazılmaz.

### 6.3 Bağlantı kesme izolasyonu

`DisconnectPlatformConnectionUseCase`:

- Yalnızca hedef bağlantıyı pasifleştirir ve o bağlantının kanallarını devre dışı bırakır.
- Yalnızca o bağlantının Keychain kayıtlarını siler.
- Yalnızca o bağlantının bekleyen yayın/zamanlamalarını hata durumuna alır.
- Seçim hedefe işaret ediyorsa etkin başka bir kanala taşır veya temizler.
- Diğer bağlantıların token, kanal, yayın ve zamanlama kayıtları etkilenmez (test: `test_disconnect_affects_only_the_target_connection`).

---

## 7. YouTube Kanal Keşfi

OAuth tamamlandığında:

1. `openidconnect.googleapis.com/v1/userinfo` ile hesap kimliği alınır (opsiyonel; hata akışı durdurmaz).
2. `channels.list?part=snippet,statistics,contentDetails&mine=true` çağrısı yapılır.
3. Dönen her kanal için şu gerçek alanlar saklanır:
   - kanal kimliği (`id`)
   - kanal adı (`snippet.title`)
   - handle (`snippet.customUrl`)
   - avatar (`snippet.thumbnails.medium/default.url`)
   - açıklama (`snippet.description`)
   - abone sayısı (`statistics.subscriberCount`; gizliyse `NULL`)
   - uploads playlist (`contentDetails.relatedPlaylists.uploads`)
4. Kanal listesi boşsa bağlantı oluşturulmaz; kullanıcıya erişilebilir kanal bulunamadığı bildirilir.
5. Keşfedilmeyen eski kanallar silinmez; `is_enabled=False` yapılır.

**API sınırları:**

- `mine=true` yalnızca grant'in sahibi olduğu/aktif olarak yönetebildiği kanalları döndürür; yalnızca yönetici/ajans erişimi olan kanallar görünmeyebilir.
- Marka hesapları Google tarafında grant kapsamına bağlıdır; bazen yeniden yetkilendirme gerekir.
- Gizli abone sayısı `NULL` olarak temsil edilir; uydurulmaz.
- YouTube Data API kota sınırları kanal keşfi ve profil çağrılarını etkileyebilir.
- `contentOwner` / CMS kanalları bu kapsamda desteklenmez.

---

## 8. Global Kanal Seçici

### 8.1 Backend

- `GET /api/v1/social/channels` — tüm etkin bağlantıların kanallarını `ChannelContext` olarak listeler.
- `GET /api/v1/social/channels/selection` — kalıcı aktif kanal.
- `PUT /api/v1/social/channels/selection` — seçimi doğrular, kanalı etkin/pasif bağlantı durumuna göre kontrol eder ve kaydeder.
- `PATCH /api/v1/social/channels/{channel_id}` — kanal etkinleştirme/devre dışı bırakma.

### 8.2 Frontend

- `ChannelProvider` (`frontend/src/context/ChannelContext.tsx`) kanal listesini ve seçimi yönetir.
- `ChannelSwitcher` (`frontend/src/components/channels/ChannelSwitcher.tsx`) ana layout üst çubuğunda `YouTube ▼` biçiminde görünür; hesaplara göre gruplu kanal listesi sunar.
- Seçim hem sunucuda (`user_channel_preferences`) hem de `localStorage` anahtarında (`tezlify.active_channel_id`) saklanır; uygulama yeniden başlatıldığında geri yüklenir.
- Kanal yoksa onboarding/boş durum gösterilir; "Hesap Ekle" akışına yönlendirir.
- Upload ve scheduler ekranları hedef kanalı açıkça gösterir (`ChannelPublishModal`, scheduler hedef banner'ı).

Kanal değiştiğinde dashboard, kanal genel bakış, videolar, analytics, yorumlar, upload hedefi ve scheduler bağlamı `ChannelContext` üzerinden yenilenir.

---

## 9. Upload ve Scheduler İzolasyonu

### 9.1 Kanal kapsamlı kullanım senaryoları

Şu use case'ler artık `channel_id` alır veya sunucu tarafında `ChannelContext` çözer:

GetDashboard, GetChannelOverview, ListChannelVideos, GetChannelVideo, UpdateChannelVideo, ListChannelPlaylists, GetChannelAnalytics, ListComments, ReplyToComment, SetCommentModeration, CreatePublish, SchedulePublish.

Frontend yalnızca kanal kimliği gönderir; token veya bağlantı kimliği göndermez. Backend kanalın etkin olduğunu ve bağlantının aktif olduğunu doğrular.

### 9.2 Upload

- `PublishVideoToYouTubeUseCase` çözümlenen bağlantının access token'ını kullanır.
- Upload öncesi `list_authorized_channel_ids(token)` çağrısıyla hedef kanalın gerçekten bu token'a ait olduğu doğrulanır.
- Uyuşmazlıkta `ChannelBindingMismatchException`; YouTube'a hiçbir istek gönderilmez.
- YouTube resumable upload uç noktası `channelId` kabul etmediği için hedef kanal yalnızca token bağıyla belirlenir; bu nedenle ön doğrulama zorunludur.
- Testlerde A kanalına yükleme A token'ı ile, B kanalına yükleme B token'ı ile yapıldığı doğrulandı.

### 9.3 Scheduler

- Her `ScheduledPublish` kaydı `channel_id` ve `platform_connection_id` taşır.
- `channel_id` yoksa iş `CHANNEL_UNRESOLVED` ile reddedilir; rastgele kanala gönderilmez.
- Her iş kendi bağlantısının token'ıyla çalışır.
- Bir bağlantının token'ı süresi dolsa/bağlantı kopsa yalnızca o bağlantının işleri hata alır; diğerleri çalışmaya devam eder (test: `test_one_expired_token_does_not_break_other_connection`).
- Bağlantı kesildiğinde yalnızca o bağlantının bekleyen yayınları hata durumuna alınır.
- Retry, kaydın `channel_id` ve `platform_connection_id` değerlerini korur; yanlış kanala gönderim yapılmaz.
- Recovery/reconciliation kanal kimliğini korur; eski ve belirsiz kayıtlar `unresolved` olarak kalır.
- Migration'da kanal atfı kesin değilse tahmin yapılmaz.

---

## 10. Analytics ve Dashboard İzolasyonu

- Kanal dashboard'u yalnızca seçili kanalın `channel_external_id` değeriyle YouTube Analytics/Data API çağrıları yapar (`ids=channel==<id>`, `channelId=<id>`).
- Global dashboard yalnızca bağlantı, hesap ve kanal sayıları ile yerel yayın/zamanlama toplamlarını gösterir.
- Global toplamlar yalnızca aynı anlamdaki metrikler ve aynı tarih aralığı için birleştirilir; farklı aralıklar karıştırılmaz.
- Gelir verisi yalnızca yetkilendirilmişse gösterilir; `monetization_revenue` yeteneği YouTube için `False` olduğundan gelir uydurulmaz.
- Kanal A verisinin kanal B dashboard'unda görünmediği test edildi (`test_dashboard_data_is_scoped_to_the_selected_channel`).
- Dashboard yanıtları veri kaynağını (Data API / Analytics API / yerel DB) etiketler.

---

## 11. Platform Yetenek Mimarisi

`PlatformCatalog` statik yetenek haritası sunar:

| Yetenek | YouTube | Instagram | TikTok |
|---|---|---|---|
| connect_oauth | ✅ | ❌ | ❌ |
| disconnect | ✅ | ❌ | ❌ |
| list_accounts / list_channels | ✅ | ❌ | ❌ |
| get_channel_profile | ✅ | ❌ | ❌ |
| list_videos / upload_video / update_video | ✅ | ❌ | ❌ |
| get_analytics | ✅ | ❌ | ❌ |
| read_comments / write_comments | ✅ | ❌ | ❌ |
| schedule_publish | ✅ | ❌ | ❌ |
| monetization_revenue | ❌ | ❌ | ❌ |

Instagram ve TikTok `implemented=False` olarak listelenir; UI'da pasif/erişilemez gösterilir. OAuth akışı, API çağrısı, örnek veri veya sahte başarı yanıtı yoktur. Yeni platform eklemek için yeni bir gateway + capability tanımı yeterlidir; çekirdek domain değişmez.

---

## 12. Test Sonuçları

**Ölçüm: 2026-11-05 18:30–18:31 (yerel)**

| Paket | Komut | Sonuç |
|---|---|---|
| Backend tümü | `.venv/bin/python -m pytest backend/tests -q` | **135 passed**, 1 warning, 9.21s |
| Stage 6.1 testleri | `.venv/bin/python -m pytest backend/tests/integration/test_multi_account_stage61.py -q` | **22 passed**, 3.46s |
| Frontend testleri | `npx vitest run` | **4 passed** (1 dosya) |
| TypeScript | `npx tsc --noEmit` | Hatasız (exit 0) |
| Frontend build | `npm run build` | Başarılı (1541 modül, 1.13s) |

Uyarı: FastAPI TestClient için Starlette `httpx` deprecation uyarısı; işlevsel hata değildir.

### 12.1 §13 senaryo → test eşlemesi

| # | Senaryo | Test |
|---|---|---|
| 1 | İlk Google hesabını bağlama | `test_connect_first_google_account_creates_isolated_connection` |
| 2 | İkinci Google hesabını bağlama | `test_second_google_account_does_not_overwrite_first` |
| 3 | Token izolasyonu | `test_tokens_are_isolated_per_connection` |
| 4 | Bir hesapta birden fazla kanal | `test_multiple_channels_under_one_google_account` |
| 5 | Global kanal listesi | `test_global_channel_list_covers_every_connection` |
| 6 | Kanal değiştirme ve kalıcılık | `test_channel_switch_persists_and_resolves_selected_channel`, `test_frontend_selector_persistence_contract` |
| 7 | Dashboard A verisinin B'ye sızmaması | `test_dashboard_data_is_scoped_to_the_selected_channel` |
| 8 | A kanalına upload'un B'ye gitmemesi | `test_upload_uses_target_channel_token_not_other_account` |
| 8b | Yetkisiz kanala upload reddi | `test_upload_refuses_channel_not_authorized_for_connection` |
| 9 | Bağımsız zamanlanmış yayınlar | `test_scheduled_publishes_remain_independent_per_channel` |
| 10 | Bir token'ın süresinin diğerini bozmaması | `test_one_expired_token_does_not_break_other_connection` |
| 11 | Bağlantı kesme izolasyonu | `test_disconnect_affects_only_the_target_connection` |
| 12 | Tekrarlanan OAuth callback | `test_duplicate_oauth_callback_does_not_create_duplicate_connection` |
| 12b | Aynı hesabın tekrar eklenmesi | `test_readding_same_google_account_updates_without_duplicate` |
| 13 | Migration'ın yayın kayıtlarını koruması | `test_migration_maps_legacy_single_account_and_preserves_records`, `test_migration_never_loses_legacy_rows` |
| 13b | Belirsiz atfın `unresolved` kalması | `test_migration_keeps_ambiguous_publish_attribution_unresolved` |
| 14 | Tek hesap legacy migration | `test_migration_maps_legacy_single_account_and_preserves_records` |
| 15 | Erişilemeyen kanal verisinin reddi | `test_inaccessible_channels_are_denied` |
| 16 | Scheduler'ın çözümlenmemiş kanalı reddetmesi | `test_scheduler_refuses_unresolved_channel` |
| 17 | Platform yetenekleri | `test_platform_capabilities_only_advertise_implemented_platforms` |
| — | Hesap endpoint'i kanal DTO serileştirmesi | `test_connections_endpoint_serializes_channel_dtos` |

Testler fake repository/port, fake token storage, fake publisher, fake gateway ve geçici SQLite veritabanı kullanır. Gerçek kanala yazma yapılmadı.

---

## 13. API ve Ortam Sınırları

1. **Resumable upload'da `channelId` yok:** Hedef kanal yalnızca OAuth token'ı ile belirlenir. Bu nedenle upload öncesi `list_authorized_channel_ids` doğrulaması zorunludur; gelecekte bu doğrulama kaldırılmamalıdır.
2. **`mine=true` keşif sınırı:** Yalnızca grant sahibinin erişebildiği kanallar döner. Ajans/yönetici erişimli kanallar veya bazı marka hesapları ek yetkilendirme gerektirebilir.
3. **Analytics kapsamı:** Kanal bazlı Analytics API kullanılır; gelir metrikleri monetization yetkisi gerektirir ve bu sürümde `monetization_revenue=False`.
4. **OAuth state deposu süreç içidir:** Uygulama yeniden başlarsa bekleyen OAuth oturumları kaybolur; kullanıcı bağlantıyı yeniden başlatmalıdır.
5. **Legacy tablolar korunuyor:** `social_accounts` veri kaybını önlemek için silinmedi. İleride ayrı, yedekli bir temizlik migration'ı değerlendirilebilir.
6. **Instagram/TikTok:** Bilinçli olarak uygulanmadı; hiçbir sahte veri veya başarı yanıtı üretilmez.

---

## 14. Açık Riskler ve Notlar

1. **Mevcut Keychain kayıtları bulunamadı:** Ölçümde `TezlifyStudio_access` ve `TezlifyStudio_refresh` için `security find-generic-password` her ikisinde de exit code `44` (bulunamadı) döndürdü. Bağlantı `reauth_required` durumunda. Bu, migration'ın token referansını değiştirmediği hâlde **Stage 6.1 öncesinden gelen ortam durumudur**; migration veri kaybına yol açmadı. Kullanıcı Ayarlar → Bağlı Hesaplar üzerinden yeniden bağlanmalıdır. Hiçbir token değeri okunmadı/yazdırılmadı.
2. **Gerçek kanalda yazma doğrulanmadı:** Upload, metadata PATCH, yorum yanıtı ve zamanlama yalnızca fake/mock ile test edildi. Canlı doğrulama kullanıcı onayı gerektirir.
3. **`scheduled_publishes` 0 satır:** Scheduler ve izolasyon testleri mevcut; kullanıcıda planlı kayıt yok.
4. **Belirsiz legacy atıf:** Birden fazla hesap bulunan kurulumlarda eski yayınlar `unresolved` kalır; bu bilinçli bir veri güvenliği kararıdır.
5. **Kanal adı:** Bağlı hesap `Resilience Channel` / `UC_RESILIENCE`; Stage 6.1 bu kimliği değiştirmedi.
6. **Çoklu süreç:** OAuth state deposu tek süreç içindir; çok işçili dağıtımda paylaşımlı depo gerekir.

---

## 15. Commit Planı

Tek yerel commit:

- `feat(studio): support multiple platform accounts and youtube channels`

Commit kapsamı: Stage 6.1 domain/persistence/migration/OAuth/gateway/API/frontend/test/report dosyaları. `STAGE_5_*` raporları, `evidence/**` ve `backend/uv.lock` kapsam dışı bırakıldı.

Push, deployment ve gerçek kanalda yazma işlemi yapılmadı.

---

**GENEL SONUÇ: PASS_WITH_NOTES**
