# YouTube Resumable Yükleme ve Hata Kurtarma Kılavuzu

Tezlify AI Video Studio, YouTube Data API v3 Resumable Upload protokolünü ve RFC 7233 kurallarını eksiksiz uygular. Büyük video dosyalarında bağlantı kopsa, sunucu kapansa veya ağ dalgalanması yaşansa dahi veri kaybı önlenir.

---

## 1. Resumable Upload Protokolü

1. **Oturum Başlatma (Initiation)**:
   - Backend `POST https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable` çağrısı yapar.
   - Google sunucusu benzersiz bir oturum URI'si döner (`Location` başlığı).
   - Bu oturum URI'si veritabanında güvenle saklanır ancak REST API istemcilerine sızdırılmaz.

2. **Parçalı Yükleme (Chunk Upload)**:
   - Video standart 4 MB (256 KB tam katı) bloklar halinde `PUT {session_uri}` ile gönderilir.
   - Her başarılı parçada Google `308 Resume Incomplete` ve `Range: bytes=0-{son_byte}` döner.
   - İlerleme yüzdesi ve onaylanan byte miktarı SQLite'a anlık yazılır.

3. **Tamamlanma**:
   - Son parça başarıyla yüklendiğinde Google `200/201 Created` yanıtı ile birlikte `video_id` döner.
   - Durum `PUBLISHED` yapılır, YouTube video URL'si (`https://youtu.be/{id}`) kaydedilir.
   - Varsa özel kapak görseli (custom thumbnail) otomatik olarak videoya iliştirilir.

---

## 2. Dayanıklılık ve Kurtarma Senaryoları

### Senaryo A: Sunucu Çökmesi veya Sürecin Kapanması (Startup Reconciliation)
- Uygulama çalışırken terminal kapatılırsa veya bilgisayar yeniden başlatılırsa:
- Backend ilk başlatıldığında (`create_app`), veritabanında askıda kalmış (`PENDING`, `UPLOADING`, `AUTHENTICATING`) "zombi" işleri tespit eder.
- Bu işlerin tamamı atomik olarak `PAUSED` durumuna ve `SERVER_RESTARTED` hata koduna geçirilir.
- Kullanıcı stüdyoyu açtığında listede "Devam Ettir (Resume)" seçeneği görür.

### Senaryo B: Oturum Süresinin Dolması (HTTP 404 Session Expiration)
- Google'ın resumable oturum URL'leri yaklaşık 24 saat sonra zaman aşımına uğrar veya geçersizleşir.
- Yükleme veya durum sorgusu sırasında HTTP 404 dönerse:
  1. `UploadSessionExpiredException` tetiklenir.
  2. Eski `upload_session_uri` temizlenir ve `uploaded_bytes` sıfırlanır.
  3. İşlem `FAILED` durumuna ve `SESSION_EXPIRED` koduna alınır.
  4. Kullanıcıya oturumun süresinin dolduğu ve temiz bir yükleme başlatması gerektiği açıkça bildirilir.

### Senaryo C: Geçici Sunucu Hataları (5xx) ve Retry-After
- Google sunucularında 500, 502, 503 veya 504 hatası alındığında:
  1. İstemci `Retry-After` HTTP başlığını inceler.
  2. Başlıkta belirtilen süre (veya üstel geri çekilme `1s, 2s, 4s...`) kadar beklenir.
  3. En fazla 3 yeniden deneme yapılır.
  4. Durum sorgulanarak Google'ın hafızasındaki son geçerli byte tespit edilir ve oradan devam edilir.

### Senaryo D: Granüler Kota ve Yetki Ayrımı (403 Forbidden)
Google API 403 hataları tek bir kategoriye indirgenmez, hassasiyetle ayrıştırılır:
- **`quotaExceeded` / `dailyLimitExceeded`**: Günlük YouTube Data API kota havuzu tükenmiştir (ayrılmış videos.insert havuzu aşımı). Pasifik Saatine (PT) göre gece yarısı otomatik sıfırlanır. Durum `FAILED (QUOTA_EXCEEDED)` yapılır. (Bkz: `docs/setup/youtube-api-quota.md`)
- **`uploadLimitExceeded`**: Kanalın günlük video yükleme sınırına veya YouTube'un kanal doğrulama kısıtlamasına takılmıştır.
- **`accessNotConfigured`**: YouTube Data API v3 Google Cloud projesinde etkinleştirilmemiştir.
- **Diğer 403 Yanıtları**: İzin veya kanal sahipliği reddi olarak kullanıcıya ayrıntılı hata mesajıyla bildirilir.

### Senaryo E: Token Süresi Dolumu ve Yenileme (Refresh Token)
- Access token 1 saatlik ömre sahiptir.
- Süresi dolduğunda macOS Keychain'den `refresh_token` okunur ve Google OAuth uç noktasından yeni bir `access_token` temin edilir.
- Kullanıcı Google Güvenlik ayarlarından uygulamanın yetkisini kaldırmışsa `REQUIRES_REAUTH` durumuna geçilir.
