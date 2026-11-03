# Tezlify AI Video Studio — Kaçırılan Görevler ve Başlatma Uzlaştırması (Startup Reconciliation)

**Son Güncelleme:** 3 Kasım 2026  
**İlgili Modül:** `ReconcileScheduledPublishesUseCase` / `PublishSchedulerService`  

---

## 1. Çevrimdışı Kalma ve Kaçırılan Görev Politikası (Missed Job Policy)

Yerel çalışan bir masaüstü stüdyo uygulamasında bilgisayar kapatılabilir, uyku moduna geçebilir veya uygulama uzun süre çalıştırılmayabilir. Bu durumda zamanı geçmiş yayın görevleri aşağıdaki kurallara göre değerlendirilir:

### Yapılandırma Parametresi
- **`SCHEDULER_MISSED_GRACE_PERIOD_MINUTES`** (Varsayılan: `60 dakika`)

### Değerlendirme Algoritması
FastAPI başlatılırken (`lifespan startup`) veya bilgisayar uyandığında `ReconcileScheduledPublishesUseCase` otomatik çalışır:

1. **Zombi Görev Temizliği (`status = 'processing'`):**
   - Uygulama aniden kapandığında (elektrik kesintisi, crash) `PROCESSING` durumunda kalmış görevler bulunur.
   - İlgili görevin son durumu incelenir: eğer YouTube resumable session URI mevcutsa `PAUSED` durumuna çekilerek kullanıcıya devam ettirme veya iptal şansı verilir.

2. **Zamanı Geçmiş Görevler (`scheduled_at_utc < now` ve `status = 'scheduled'`):**
   - **Gecikme Süresi <= Grace Period (örn. 60 dk):**
     Görev normal kabul edilir; arka plan işçisi sonraki döngüde görevi `PROCESSING` durumuna alarak derhal yayınlar.
   - **Gecikme Süresi > Grace Period (örn. 2 saat, 2 gün önce planlanmış):**
     İçeriğin planlanan takvim bağlamı bozulduğu için kullanıcı izni olmaksızın YouTube'a otomatik fırlatılmaz!
     Görev doğrudan `MISSED` (Kaçırıldı) durumuna geçirilir ve veritabanına `MISSED_DUE_TO_OFFLINE` hata kodu kaydedilir.
     Kullanıcı arayüzde bu görevi görür ve tek tıkla **"Yeniden Dene / Yeni Zamana Planla"** butonuna basarak görevi yeniden kuyruğa alabilir.

---

## 2. Hata Türleri ve Otomatik Tekrar Deneme (Retry Backoff)

| Hata Tipi | Hata Kodu / Örnek | Davranış | Tekrar Deneme (Retry)? |
|---|---|---|---|
| **Geçici Ağ Hatası** | `ConnectionError`, `Timeout`, `503 Service Unavailable` | `attempt_count += 1`. `now + retry_delay_minutes` hesaplanarak ileri zamana ötelenir. | **EVET** (Max attempts sınırına kadar) |
| **Kota Aşımı** | `QUOTA_EXCEEDED`, `uploadLimitExceeded` | Görev anında `FAILED` durumuna çekilir. `error_message` kaydedilir. | **HAYIR** (Gereksiz kota tüketimi engellenir) |
| **Yetki Kaybı** | `REQUIRES_REAUTH`, `invalid_grant` | Görev `FAILED` yapılır. Kullanıcıya arayüzde yeniden OAuth bağlantısı bildirilir. | **HAYIR** (Kullanıcı etkileşimi şarttır) |
| **Medya Dosyası Silinmiş** | `FILE_NOT_FOUND`, `INVALID_MEDIA` | Diskten dosya silinmişse görev `FAILED` yapılır. | **HAYIR** |

---

## 3. Kurtarma Senaryosu Test Matrisi

- `test_reconcile_scheduled_publishes_on_reboot`: Grace period içi ve dışındaki görevlerin doğru sınıflandırıldığını doğrular.
- `test_process_due_transient_error_retry_backoff`: Ağ kopukluklarında linear/exponential gecikme ile tekrar denendiğini doğrular.
- `test_process_due_permanent_quota_error`: Kota tükenmesinde döngüye girmeden durdurulduğunu garantiler.

---

## 4. Aşama 3.1 Çökme ve Güvenilirlik Kurtarma Senaryoları

Aşama 3.1 kapsamında eklenen ve `backend/tests/integration/test_scheduler_reliability_and_recovery.py` altında uçtan uca doğrulanan 10 kritik senaryo:

1. **Uzak YouTube Başarısı / Yerel DB Hatası Ayrışması:**
   YouTube video ID döndükten sonra DB çökerse veya işlem öldürülürse, başlatma uzlaştırması görevi mükerrer yükleme yapmadan `PUBLISHED` olarak kurtarır.
2. **Kopuk Yanıt / Son Parça Tamamlanması:**
   Son bayt gönderildikten sonra HTTP bağlantısı kopsa dahi, `query_upload_status` üzerinden `video_id` elde edilerek kayıt `PUBLISHED` yapılır.
3. **Mükerrer Zamanlanmış Görev Koruması:**
   Aynı medya için oluşturulmuş ikinci bir zamanlanmış görev, birincisi yayınlandığı anda YouTube'a ikinci bir dosya göndermez; anında `PUBLISHED` olarak tamamlanır.
4. **Zarif Sunucu Kapanması (Graceful Pause):**
   Chunk yükleme sırasında `stop_checker` sinyali alındığında yükleme `PAUSED` durumuna geçer ve resumable URI güvenle saklanır.
5. **Worker Öncesi Sıralı Uzlaştırma (Strict Order Reconciliation):**
   `ReconcileScheduledPublishesUseCase` daemon worker thread başlamadan önce senkronize çalışır; böylece eski zombi görevler temizlenmeden yeni işçi tetiklenmez.
6. **SQLite Transaction Rollback:**
   Yükleme başlatma sırasında veritabanı hatası oluşursa `commit` edilmez; transaction tamamen geri alınarak kütüphane tutarlılığı korunur.
7. **Bozuk Resumable Session URI Kurtarma:**
   YouTube resumable session süresi dolmuşsa (404/410), sistem sessizce kilitlenmez; temiz bir hata ve tekrar deneme durumu atanır.
8. **Çoklu Scheduler Örneği Eşzamanlılık Koruması:**
   İki bağımsız scheduler nesnesi aynı anda `tick()` çalıştırdığında optimistik sürüm kilidi sayesinde yalnızca tek biri işlem yapar.
9. **Yaz Saati İleri Saat (Spring Forward) Atlaması:**
   Zaman diliminde var olmayan duvar saatleri (örn. 02:30 AM) API seviyesinde doğrudan `422` ile reddedilir.
10. **Ağ Zaman Aşımı ve Geri Çekilme (Exponential Backoff):**
    Timeout alan görevler `attempt_count` artırılarak güvenli bekleme süresine ötelenir.
