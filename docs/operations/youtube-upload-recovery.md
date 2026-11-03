# YouTube Resumable Yükleme ve Hata Kurtarma Kılavuzu

Tezlify AI Video Studio, YouTube Data API v3 Resumable Upload protokolünü tam olarak destekler. Büyük video dosyalarında bağlantı kopsa dahi yükleme baştan başlamaz.

## 1. Resumable Upload Protokolü Nasıl Çalışır?

1. **Oturum Başlatma (Initiation)**:
   - Backend `POST https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable` çağrısı yapar.
   - Google sunucusu bir oturum URI'si döner (`Location` başlığı).
   - Bu oturum URI'si SQLite'ta `upload_session_uri` alanına kaydedilir.

2. **Parçalı Yükleme (Chunk Upload)**:
   - Video standart 4 MB (256 KB katları) bloklar halinde `PUT {session_uri}` ile gönderilir.
   - Başarılı parçalarda Google `308 Resume Incomplete` ve `Range: bytes=0-{son_byte}` döner.
   - İlerleme yüzdesi hesaplanır ve SQLite'a anlık yazılır.

3. **Sonlandırma**:
   - Son parça yüklendiğinde Google `200/201 Created` yanıtı ve video ID'sini döner.
   - Durum `PUBLISHED` yapılır, YouTube video URL'si (`https://youtu.be/{id}`) kaydedilir.

## 2. Hata ve Kurtarma Senaryoları

### Senaryo A: Ağ Bağlantısı Koptu veya Uygulama Kapandı
- Yayın kaydı `PAUSED` durumuna geçer.
- Kullanıcı stüdyoyu tekrar açtığında listede "Devam Ettir (Resume)" butonu görür.
- Butona basıldığında:
  1. `PUT {session_uri}` ile boş gövde ve `Content-Range: bytes */total_bytes` gönderilir.
  2. Google, hafızasındaki son byte numarasını döner (örneğin 24 MB'ın 16 MB'ı alınmış).
  3. Video dosyası yerel diskte 16. MB'a kadar `seek()` edilir ve yükleme kalan parçadan devam eder.

### Senaryo B: Günlük API Kotası Aşıldı (Quota Exceeded)
- Google YouTube API, günlük 10.000 birim kota tahsis eder (1 video yükleme = 1600 birim).
- Kota aşıldığında API HTTP 429 döner ve `QuotaExceededException` fırlatılır.
- Stüdyo durumu `FAILED` yapar ve Pasifik Saatine göre (PST) gece yarısı sıfırlanacağı bilgisini kullanıcıya sunar.

### Senaryo C: Access Token Süresi Doldu
- Access token 1 saatlik ömre sahiptir.
- Arka planda `SocialAccount.is_token_expired()` denetlenir.
- Süresi dolmuşsa Keychain'den `refresh_token` alınır, Google'a yeni token sorulur ve sessizce yenilenir.
- Eğer refresh token kullanıcı tarafından Google Güvenlik sayfasından iptal edilmişse, kayıt `REQUIRES_REAUTH` durumuna geçer ve kullanıcıya "Yeniden Yetki Verin" uyarısı gösterilir.
