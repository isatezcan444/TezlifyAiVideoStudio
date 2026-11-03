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
