# YouTube Data API v3 Güncel Kota ve Hız Sınırı (Rate Limit) Modeli

**Son Doğrulama Tarihi:** 3 Kasım 2026  
**Resmî Başvuru Kaynakları:**
- [YouTube Data API Overview - Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost)
- [YouTube Data API Upload Protocol Docs](https://developers.google.com/youtube/v3/guides/uploading_a_video)

---

## 1. Kota Mimarisi ve Ayrılmış Havuzlar

Google Cloud üzerinde YouTube Data API v3 kullanan her proje için iki temel kota havuzu tanımlanır:

### A. Video Yükleme Havuzu (`videos.insert`)
- **İşlem Tipi:** Resumable video yükleme başlatma ve tamamlama.
- **Varsayılan Limit:** Günlük 100 çağrı / gün (standart geliştirici projesi).
- **Maliyet:** Çağrı başına 1 birim (eski belgelerde geçen sabit 1.600 birim maliyeti güncel sürümde tekil video yükleme havuzu bazında 100 video/gün tavanı olarak yapılandırılmıştır).
- **Sıfırlanma Zamanı:** Pasifik Zaman Dilimine (PT - Pacific Time) göre gece yarısı (00:00 PST/PDT).

### B. Genel Okuma ve Liste Havuzu (Read / List Requests)
- **İşlem Tipleri:** `channels.list`, `playlistItems.list`, `thumbnails.set`, `videos.list`.
- **Varsayılan Limit:** Günlük 10.000 birim kota havuzu.
- **Maliyetler:** Basit `list` işlemleri genellikle 1 birim, kanal profili sorguları 1 birimdir.

---

## 2. Kota Aşımı (`quotaExceeded`) ile Kanal Sınırı (`uploadLimitExceeded`) Ayrımı

Tezlify AI Video Studio hata yönetiminde bu iki durum kesin olarak ayrıştırılır:

1. **`quotaExceeded` / `dailyLimitExceeded` (HTTP 403):**
   - Google Cloud projenizin günlük API çağrı kotası tükenmiştir.
   - Bu durum proje bazlıdır; stüdyo görevi `FAILED` yapar ve `QUOTA_EXCEEDED` hatası kaydeder. Gece yarısı PT saatinde otomatik sıfırlanır.

2. **`uploadLimitExceeded` (HTTP 403):**
   - API kotası olsa bile YouTube kanalının kendi günlük video yükleme sınırına veya doğrulanmamış hesap güvenlik kısıtlamasına takılmıştır.
   - Yeni veya telefonla doğrulanmamış YouTube kanallarında Google ilk günlerde günde 1-5 video yüklemesine izin verebilir.
   - Kanal doğrulandıkça bu sınır kademeli artar.

---

## 3. Yapılandırılabilirlik ve Kota Koruma Prensipleri

1. **Kota Sabitlenemez:** Uygulama içerisinde günlük video sınırı kod içine değiştirilemez rakam olarak gömülmemiştir; Google'ın her projeye özel tahsis ettiği kotalar baz alınır.
2. **Tekrar Deneme Sınırı (Retry Limit):** Kota hatası (`QUOTA_EXCEEDED` veya `uploadLimitExceeded`) alındığında otomatik scheduler tekrar deneme YAPMAZ; görevi durdurarak gereksiz API harcamasını engeller.
3. **Idempotency:** Yarıda kalan yüklemeler `query_upload_status` ile devam ettirilir; aynı video için yeni bir `videos.insert` oturumu açılmaz.
