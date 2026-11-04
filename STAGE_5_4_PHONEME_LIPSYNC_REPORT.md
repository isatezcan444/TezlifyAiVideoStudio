# STAGE 5.4 — REAL PHONEME / VISEME-BASED LIP-SYNC

**Proje:** Tezlify AI Video Studio
**Aşama:** Stage 5.4 — Gerçek Fonem/Viseme Tabanlı Dudak Senkronizasyonu
**Tür:** Kodlama
**Branch:** `main`
**Başlangıç commit'i:** `e3d0bda0754ea9bcff87be6ae2990cf43c6f4134` (Stage 5.3 bitiş commit'i — `git rev-parse HEAD` ile doğrulandı; raporda yazılı SHA kullanılmadı)
**Rapor tarihi:** 2026-11-05
**Ortam:** Blender 5.2.3 LTS · FFmpeg 9.0.2 · Uygulama Python 3.14.7 · İzole alignment Python 3.12.13 · macOS Darwin 27.0.0 arm64 (16 GB RAM, 10 CPU)

---

## 0. SONUÇ ÖZETİ

**Gerçek Türkçe fonem zamanlaması elde edildi, Blender ağız animasyonu bu zamanlamayı takip etti ve gerçek render karelerinde doğrulandı.**

| Ölçüm | Değer |
|---|---|
| Alignment motoru | **Yerel CTC forced alignment** (wav2vec2 Türkçe akustik model) |
| Ağdan veri gidiyor mu? | **Hayır** — tamamen lokal CPU |
| ElevenLabs API anahtarı | **Yok** (`is_configured: False`) — bu yol test edilmedi, edilmiş gibi gösterilmedi |
| Ses kaynağı | macOS `say` **Yelda (tr_TR)** — kurulu olduğu doğrulandı |
| Hizalanan diyalog | 4/4, toplam **102 viseme segmenti** |
| İlk fonem offset'i | **0.02 s** (ses başlangıcına göre) |
| Planlanan aralık ↔ ses süresi | 4/4 diyalogda **birebir aynı** (±0.001 s) |
| OPEN ailesi vs CLOSED ağız koyuluk oranı | **0.2865 vs 0.0888** (3.2×) |
| Ağız bölgesi piksel farkı (OPEN↔CLOSED) | **%37.2 – %70.3** |
| Konuşma sonrası ağız yüksekliği | 0.081 m → **0.042 m** (kapandı) |
| Backend / Frontend / build / doctor / E2E | **309 passed / 27 passed / OK / OK / OK** |

---

## 1. BAŞLANGIÇ VE BİTİŞ COMMIT SHA

| | Değer |
|---|---|
| Başlangıç (Stage 5.3 bitiş) | `e3d0bda0754ea9bcff87be6ae2990cf43c6f4134` |
| Branch | `main` |
| Stage 5.4 implementasyon commit'i | `da1dc6416f2629ac20371e903a5b08b65c298bd9` — `feat(studio): implement phoneme-based character lip sync` (44 dosya, +9546 / −23) |
| Bu satır | Bir commit kendi SHA'sını içeremeyeceği için rapor, SHA'sı bilinen tek dosya olarak ayrı bir docs commit'i ile güncellenmiştir |
| Push / deploy | **Yapılmadı.** `origin` tanımlı; `main` şu an `origin/main` önünde — önceki aşamalarda olduğu gibi yalnızca yerel commit |

---

## 2. ORTAM VE MİMARİ DENETİMİ (Brief Bölüm 2 — gerçek kod/ortam cevapları)

Denetim üç **varsayımın yanlış olduğunu** ortaya çıkardı; rapor buna göre şekillendi.

### 2.1 ElevenLabs timestamp yolu

Kod `with-timestamps` endpoint'ini **zaten çağırıyor** ve `alignment` JSON'unu alıyor
([elevenlabs_client_impl.py:219](backend/src/tezlify_studio/infrastructure/ai/elevenlabs_client_impl.py)).
Ancak:
- Anahtar tanımlı değil → **bu yol hiç çalıştırılamadı, test edilmiş gibi raporlanmadı.**
- Yanıt yalnızca **karakter-düzeyi**; fonem istenmiyor, `phoneme_alignment` flag'i yok.
- Sonuç `alignment_json` string olarak taşınıp `execute_render_job_use_case.py:143`'de **çöpe atılıyor**.
- Cache'ten dönen seslerde `alignment_json = None` — yani cache hit'te zamanlama tamamen kayboluyor.

### 2.2 macOS `say`

`Yelda (Türkçe (Türkiye)) tr_TR` kurulu (185 ses içinde doğrulandı). **Hiçbir zamanlama metadata'sı üretmiyor.** Denetim sırasında `say -v` (boş döner) ile `say -v '?'` (185 satır) farkından kaynaklı bir yanlış-olumsuz okumam oldu ve düzeltildi; mevcut demo sesleri gerçek Türkçe ses.

### 2.3 Karakter ağız geometrisi — shape key YOK

Tüm nesneler Blender ile sorgulandı: `char_ali.blend` içinde 46 nesnenin **hiçbirinde** shape key yok (`SHAPEKEYS= None`), repo genelinde `shape_keys` geçen tek bir satır bile yok. Brief'in "önce bunu kanıtla" maddesi gereği kanıt üretildi; bu yüzden **shape key yerine ölçüme dayalı transform** seçildi.

### 2.4 Ölü şema yeniden kullanıldı

`SceneDialogue.visemes` ve `DialogueViseme` zaten mevcuttu ve `scene_graph.model_dump()` ile Blender manifestine **zaten ulaşıyordu** — ama hiçbir yerde okunmuyordu; tek yazar `template_story_planner_impl.py:361` idi ve sesle ilgisi olmayan sentetik `0.35 s` adım değerleri yazıyordu. Yeni sınıf yığını üretmek yerine bu ölü kanal gerçek sözleşmeye çevrildi (brief: "uygun bir yapı varsa gereksiz yeni sınıf oluşturma").

### 2.5 Mevcut ağız animasyonunun gerçek durumu

`render_worker.py` diyalog boyunca `Mesh_Mouth.scale.z`'yi **sabit 4-kare döngüyle** açıyor; genlikler karakter id hash'inden geliyor, konuşma içeriğinden değil. Bu brief'in tanımladığı gibi gerçek lip-sync değil.

---

## 3. ALIGNMENT MİMARİSİ KARARI VE YOL UNTUKLARI

### 3.1 A yolu (ElevenLabs) — kullanılamaz
Anahtar yok. Kod var ama doğrulanamadı. **Rapor bunu "çalışıyor" olarak sunmuyor.**

### 3.2 MFA denemesi — bloke (dürüst negatif sonuç)
Brief'ın "izole subprocess/ayrı Python ortamı" izniyle önce Montreal Forced Aligner denendi:
- `Montreal_Forced_Aligner 3.4.3` python3.12 venv'ine kuruldu (591 MB).
- **Çalışmıyor:** paket `_kalpy` (derlenmiş Kaldi eklentisi) import ediyor, ama `pip show` Requires listesinde `kalpy` **yok** ve PyPI'da `kalpy` **404** dönüyor. `conda` kurulu değil.
- Sonuç: pip ile bu makinede MFA kurulamaz. Kurulan 591 MB'lık ölü venv **silindi** (kullanıcı onayıyla).

### 3.3 B yolu — kabul edildi ve kanıtlandı
Yerel, Türkçe destekli, telefona veri göndermeyen zincir:

```
HuggingFace reachable (anonim erişim, gated değil)
  └─ Baybars/wav2vec2-xls-r-300m-cv8-turkish
       • mimari:            Wav2Vec2ForCTC, vocab_size 41
       • lisans:            apache-2.0
       • boyut:             pytorch_model.bin 1.26 GB (lm_* dil modeli indirilmez)
       • sözlük:            a–z + â ç ë î ö ü ğ ı ş + '|' (kelime ayracı)
       • Türkçe harfler:    ç ğ ı ö ş ü — hepsi sözlükte (doğrulandı)
       • blank:             38  (= tokenizer.pad_token_id; varsayılan 0 DEĞİL)
       • frame çözünürlüğü: 20.1 ms  (ölçüldü, varsayım değil)

ffmpeg (mevcut bağımlılık) → 16 kHz mono wav
  → torch softmax posteriors  (T, 41)
  → ctc_segmentation (bilinen transkripti sese hizalar)
  → timings[] (saniye) → karakter interval'ları
  → Türkçe harf → viseme eşlemesi → Blender keyframe
```

**Neden karakter-düzeyi yeterli:** Türkçe ortografisi fonemik; modelin karakter çıktıları doğrudan ünsüz/ünlü zamanlaması veriyor. Brief'in viseme tablosu da zaten **harf** bazlı tanımlı (`p, b, m → CLOSED`). Bu, ElevenLabs'in verdiği karakter-zamanı granularity'siyle aynı seviye. **Fonem-özel bir akustik model kullanılmış gibi iddia edilmiyor** — bilinen bir sınırlama olarak Bölüm 11'de.

### 3.4 Bağımlılık izolasyonu
Uygulama venv'i Python 3.14 ve **bilerek ML'den arındırıldı** (fastapi/sqlalchemy/pydantic). torch 2.15.0 + transformers 5.22.1 + ctc-segmentation 1.7.5 yalnızca `tools/alignment-venv` (python3.12) içinde; oraya **subprocess + iki JSON dosyası** ile erişiliyor. Kurulum: `scripts/setup_alignment_env.sh`.

---

## 4. DOMAIN MODELİ VE VERİ SÖZLEŞMESİ

Yeni: [speech_alignment.py](backend/src/tezlify_studio/domain/value_objects/speech_alignment.py)

| Model | Alanlar |
|---|---|
| `PhonemeSegment` | `start_time`, `end_time`, `phoneme`, `speaker_id`, `confidence`, `source` |
| `VisemeSegment` | aynı + `viseme: MouthViseme` |
| `AlignmentRequest` | diyalog + ses dosyası + süre; `cache_key(model_id)` içerik adresi üretir |
| `DialogueAlignment` | segmentler + `audio_duration_seconds`, `source`, `provider`, `model_id`, `fingerprint`; `is_real`, `covered_seconds`, `first_start_seconds`, `last_end_seconds`, `clamped_to_audio()` |
| `AlignmentSource` (enum) | `ctc_forced`, `elevenlabs_timing` (gerçek) · `estimated`, `legacy_flap`, `none` (**gerçek değil**) |

Kurallar ve karşılıkları:

| Brief kuralı | Uygulama |
|---|---|
| Negatif süre yok, `end > start` | Her segmentte `model_validator`; `InvalidAlignmentException` |
| Zamanlar ses dosyası referanslı | Modül docstring'i tek referansı sabitler: **ses başlangıcından saniye**. Sahne offset'i uygulamada bir kez eklenir |
| Ses süresini aşan segment kontrollü | `clamped_to_audio()`: kuyruk kırpılır, sesten sonra **başlayan** segment atılır (sıfır uzunluğa sıkıştırılmaz) |
| Çakışan segment doğrulanmalı | `_validate_ordering` — constructor'da reddedilir, clamp ile "kurtarılamaz" |
| Bozuk alignment render'ı çökertmemeli | Provider boş dict döner, resolver graph'ı değiştirmeden döner, worker legacy flap'e düşer |
| Deterministik tekrar | `fingerprint` içerik adreslidir; **timestamp bilinçli yok**. Test: aynı girdi → bit-birebir çıktı |
| Cache edilebilir | `data/alignment_cache/{sha256}.json`; ses baytı/metin/konuşmacı/model değişirse anahtar değişir |
| Geriye dönük uyumluluk | `DialogueViseme` yeni alanlar **varsayılanlı**; eski `time`/`shape` duruyor; stored JSON'lar doğrulanmaya devam ediyor (18 eski domain testi geçiyor) |

`DialogueViseme` genişletmesi ([scene_graph.py:59](backend/src/tezlify_studio/domain/value_objects/scene_graph.py)): `end_time`, `viseme`, `phoneme`, `confidence`, `source`. **`source` varsayılanı `estimated`** — yani Stage 5.4 öncesi yazılmış hiçbir kayıt "ölçüldü" diye okunamaz.

---

## 5. TÜRKÇE FONEM → VISEME HARİTASI

[viseme_mapper.py](backend/src/tezlify_studio/domain/services/viseme_mapper.py) — brief'in istediği 10 grup eksiksiz:

| Viseme | Türkçe harfler |
|---|---|
| REST | sessizlik, noktalama, kelime arası |
| CLOSED | p, b, m |
| FV | f, v |
| DENTAL | t, d, n, l, r |
| SIBILANT | s, z, ş, j, ç, c |
| VELAR | k, g, ğ, h |
| OPEN | a, e |
| WIDE | i, ı |
| ROUND | o, ö |
| NARROW_ROUND | u, ü, y, w |

Kritik tuzak: Python'ün `str.lower()` çağrısı `İ → "i̇"` (combining dot) üretir ve karakter sessizce düşer. Türkçe katlama tablosu açıkça tanımlandı: `İ→i`, `I→ı`. Parametrize test bunu 7 büyük harf için kilitliyor.

Yumuşatma kuralları — hiçbiri zaman kaydırmıyor:
- `collapse_repeats` yalnızca **bitişik** aynı-shape segmentleri birleştirir (dış sınırlar sabit).
- `absorb_short_segments` bir kareden kısa segmentleri komşuya yedirir (24 fps'de ~42 ms altı ayrı poz üretilemez).
- `insert_rest_between_gaps` >0.12 s boşluklarda ağzı kapatır.
- Birleşmede güven **en zayıf** değeri alır; güven yoksa `None` kalır — **1.0 uydurulmaz.**

---

## 6. BLENDER AĞIZ ANİMASYONU — ÖLÇÜME DAYALI KARAR

### 6.1 Eksen keşfi (varsayım değil, piksel ölçümü)

İlk ölçümüm hatayı gösterdi: `view_layer.update()` çağırmadığım için `matrix_world` (0,0,0) dönüyordu ve kamera karakterin **ayakkabılarına** bakıyordu — tüm varyantlar %0 fark verdi. Düzeltince:

Ağız silindiri `rotation_euler.x = 90°`, rest ölçeği `(1.2, 0.6, 0.4)`; world bbox **genişlik 0.084 m / derinlik 0.008 m / yükseklik 0.042 m**.

| Transform | Ağız bölgesi piksel değişimi |
|---|---|
| `scale.z × 2` — **mevcut kodun animasyonladığı kanal** | **%0.19** ← fiilen görünmez |
| `scale.x × 2` (genişlik) | %8.41 |
| `scale.y × 2` (dikey açılma) | %10.54 |
| `location.z − 0.05` (çene) | %22.55 |

**Sonuç:** Stage 5.2'deki "ağız çırpma" animasyonu derinlik ekseninde olduğu için ekranda neredeyse hiç görünmüyordu. Gerçek viseme sistemi üç kanalı birlikte sürmeli.

### 6.2 Poz tablosu

[mouth_poses.py](backend/src/tezlify_studio/domain/services/mouth_poses.py) — **saf stdlib**: Blender'ın Python'unda pydantic yok; `camera_framing` için aynı kısıdı ilk başta ben de ihlal ettim (`viseme_mapper` pydantic VO import ediyordu → worker `ModuleNotFoundError: pydantic`). Poz tablosu bu yüzden ayrıştı ve worker ile backend testleri **aynı sayıları** okuyor.

Pozlar karakterin **kendi rest değeri üzerinden çarpan** olarak tanımlı (mutlak değil), çünkü cheerful ile neutral ağız farklı; Ali ve Ayşe'nin Stage 5.2 kimlikleri korunuyor.

Doğrulanan ayırt edilebilirlik (360×360 yakın plan, 45 çift):

| Ölçüm | Değer |
|---|---|
| En düşük çift farkı | **%2.96** (REST↔SIBILANT) |
| %2 altında çift | **0 / 45** |
| Medyan çift farkı | %9.29 |
| Yüz bbox'ı dışına taşan poz | **0 / 10** (x ve z eksenlerinde ayrı ayrı kontrol) |

`POSE_LIMITS` ile her poz çalışma anında da kırpılıyor; interpolasyon **LINEAR** (Bezier overshoot mesh'i yüzün dışına itebilirdi).

### 6.3 Rest transform'un korunması

Idle bloğu ağzın rest ölçeğini `(1,1,1)` ile eziyordu — viseme çarpanları bu bozulmuş değere göre hesaplanırdı. Rest artık **import sonrası, keyframe'lerden önce** yakalanıyor (`rest_mouth`) ve hem speaker hem listener yolunda kullanılıyor.

---

## 7. RENDER PIPELINE ENTEGRASYONU

Akış brief'teki zincirin tamamını kuruyor:

```
SceneDialogue ──> Audio Asset ──> Speech Alignment ──> Phoneme Segments
     │                                 (subprocess, izole venv)
     └──> LipSyncResolver ──> SceneDialogue.visemes ──> render_manifest.json
                                     │
                          render_worker.measured_visemes()
                             ├─ source ölçüldüyse → viseme keyframe
                             └─ değilse            → legacy flap (etiketli)
                                     │
                            Blender kareleri ──> FFmpeg composition ──> MP4 + AAC
                                                          └─> RenderOutputMetadata.lip_sync
```

- **Offset disiplini:** viseme zamanları diyalog-göreli kalır; sahne/diyalog offset'ini yalnızca worker ekler. Test: `test_resolver_does_not_double_apply_the_dialogue_offset`.
- **FPS sabit kodlanmadı:** `frame = abs_start + round(start * fps)` — 24/25/30/60 için ayrı ayrı doğrulandı.
- **Konuşmacı izolasyonu:** yalnızca diyaloğun `character_id`'si animasyonlanır; listener üç kanalda da rest'e keyframe'lenir.
- **Cache:** aynı ses+metin+model yeniden hizalanmaz (test: ikinci çağrıda worker hiç çağrılmıyor).
- **Availability ayrımı:** `align()` önce cache'e bakar; venv silinmişse bile diskteki ölçülmüş sonuç kullanılır. Availability yalnızca **yeni** hizalamayı kapılar.
- **Hata davranışı:** worker çökerse/timeout olursa/bozuk JSON dönerse provider `{}` döner, resolver graph'ı değiştirmez, worker legacy flap'e düşer ve **raporda `real_lip_sync: false` yazar.** Render'ı asla düşürmez.

---

## 8. FRONTEND DURUMU

Yeni ekran yok. Render metadata'sına `lip_sync` özeti eklendi (BLENDER → composition → `output_metadata`, API zaten jenerik Dict taşıyor) ve ExportStep'e tek satır eklendi:

| Durum | Etiket |
|---|---|
| Ölçülmüş segment var | `Gerçek lip-sync · 2/2 konuşmacı` |
| Hepsi fallback | `Basit ağız animasyonu (alignment yok)` |
| Kısmi | `Gerçek lip-sync · 1/3 konuşmacı` |
| Stage 5.4 öncesi render | `Eski render (lip-sync bilgisi yok)` |

Kural testi: fallback durumunda etiket **"Gerçek lip-sync" içeremez** — 4 frontend testi bunu kilitliyor. Kullanıcıya alignment motorunun yerel mi API tabanlı mı olduğu bu satırda dürüstçe görülüyor; `LIP_SYNC_ENABLED=false` ile varsayılan davranış bozulmadan kapatılabilir.

---

## 9. GERÇEK RENDER KANITLARI

### 9.1 Ses → alignment → kare (evidence/stage_5_4/demo)

4 gerçek Türkçe cümle macOS `say`/Yelda ile üretildi, **o seslerin kendisi** hizalandı:

| Diyalog | Konuşmacı | Viseme sayısı | İlk fonem | Son bitiş | Ses süresi | Kuyruk boşluğu |
|---|---|---|---|---|---|---|
| Merhaba Ayşe, bugün nasılsın? | char_ali | 24 | 0.02 s | 1.92 s | 2.191 s | 0.271 s |
| Çocuklar dışarıda oyun oynuyor. | char_ayse | 25 | 0.02 s | 2.06 s | 2.384 s | 0.324 s |
| Üç küçük kuş ağaçta ötüyor. | char_ali | 21 | 0.02 s | 2.02 s | 2.343 s | 0.323 s |
| Bugün birlikte güzel bir kahve içelim. | char_ayse | 32 | 0.02 s | 2.40 s | 2.676 s | 0.276 s |

Toplam **102 viseme segmenti**, ortalama güven **0.2775** (posterior ortalama — gerçek ölçüm; ilk denememde `char_probs`'ın sıfırla-initialized alanını okuyup 1.0000 "güven" üretmiştim, o metrik çöpe atıldı ve doğru kaynaktan yeniden hesaplandı).

**Hizalama gerçekten içeriği takip ediyor** — `Merhaba Ayşe` satırının ölçülen zaman çizelgesi:

```
m[0.02-0.10] e[0.10-0.18] r[0.18-0.24] h[0.24-0.30] a[0.30-0.40] b[0.40-0.46] a[0.46-0.48]
   (boşluk 0.48-0.58)  a[0.58-0.68] y[0.68-0.76] ş[0.76-0.84] e[0.84-0.86]
   (boşluk 0.86-0.96)  b[0.96-1.02] u[1.02-1.10] g[1.10-1.16] ü[1.16-1.22] n[1.22-1.24]
   (boşluk 1.24-1.30)  n[1.30-1.36] a[1.36-1.48] s[1.48-1.56] ı[1.56-1.64] l[1.64-1.76]
                       s[1.76-1.84] ı[1.84-1.90] n[1.90-1.92]
```

Kelime aralıkları konuşmacının gerçekten durakladığı yerlere düşüyor ve segment süreleri **eşit değil** (24 segmentin 8'i ortalamadan >20 ms farklı; 32 segmentlinin 16'sı). Eşit-bölme olsaydı bu sayı 0 olurdu.

### 9.2 Kare bazlı kontrast

Ağız cropping'i **tahminle değil** worker'ın kendi izdüşümüyle yapıldı (ilk denememde sabit bir kutu kullandım; 9:16 two-shot'ta kutı duvara denk geldiği için fark %0.4 gibi yanlış çıktı — ölçüm hatasıydı, animasyon değil).

| Ölçüm | Sonuç |
|---|---|
| OPEN ailesi ortalama koyuluk oranı | **0.2865** |
| CLOSED ortalama koyuluk oranı | **0.0888** |
| OPEN↔CLOSED ağız bölgesi piksel farkı | **%37.15 – %70.30** (12 çift) |
| Konuşma sırası max ağız yüksekliği | 0.08115 m |
| Konuşma sonrası min ağız yüksekliği | **0.04209 m** → kapandı ✓ |
| Siyah kenar bandı (4 A/V karesi) | 0.000 / 0.000 / 0.000 / 0.000 |

Görseller: `demo/phoneme_contact_sheet.png` (CLOSED/OPEN/NARROW_ROUND/SIBILANT kareleri, ağız kutusu işaretli), `demo/ali_*.png` (24 fonem karesi), `composition_av/av_*.png`.

### 9.3 Tam üretim zinciri — muxed A/V dosyası

`SceneDialogue → ses → alignment → viseme → Blender → FFmpeg composition`:

```
data/studio_projects/stage54_composition_av/renders/comp_av_9x16/comp_av_9x16.mp4
data/studio_projects/stage54_composition_av/renders/comp_av_9x16/subtitles.srt
```

| FFprobe | Değer |
|---|---|
| çözünürlük / DAR / SAR | 1080×1920 · 9:16 · 1:1 |
| codec / pix_fmt | h264 / yuv420p |
| frame rate / süre | 30/1 · 9.733 s |
| ses | **aac @ 44100 Hz, 2 kanal** |
| `lip_sync` | `real_lip_sync: True`, `speakers_aligned: 2/2`, her iki konuşmacı `viseme` |

`t=3.60 s` karesinde o sırada konuşan **Ayşe'nin ağzı açık**, dinleyen **Ali'nin kapalı** — "Çocuklar dışarıda oyun oynuyor." altyazısıyla birlikte.

---

## 10. TEST SONUÇLARI

| Koşu | Sonuç |
|---|---|
| Backend `pytest backend/tests -q` | **309 passed**, 1 warning (önceden var olan Starlette `httpx` deprecation), 407 s |
| Frontend `vitest run` | **27 passed** (5 dosya; +4 yeni ExportStep lip-sync testi) |
| `npm run build` (tsc + vite) | OK, hatasız |
| `scripts/doctor.py` | OK (Python 3.14.7, Node v24.15.0, FFmpeg/FFprobe, Blender, medya dizini, SQLite) |
| `scripts/verify_e2e.py` | OK — 10 adım tamam (health, import+SHA-256, katalog, HTTP 206, 409 duplicate, kalıcılık, güvenli silme, YouTube, scheduler) |

Yeni testler (86 backend + 4 frontend):

| Dosya | Kapsadığı şey |
|---|---|
| `unit/test_viseme_mapping.py` (57) | 10 viseme grubu, Türkçe harf/katlama (İ/I dâhil), noktalama, yumuşatma zaman korulumu, poz limitleri, segment/alignment doğrulamaları, içerik adresli cache |
| `unit/test_speech_alignment_pipeline.py` (19) | Subprocess protokolü, absolute path, cache hit/invalidate/bozuk cache, worker failure/timeout/bozuk yanıt, resolver fallback + offset disiplini + graph mutasyon yok |
| `integration/test_lipsync_blender_render.py` (10) | **Gerçek Blender render'ında**: viseme mode, keyframe'lerin aligner zamanlarıyla birebir eşleşmesi, OPEN↔CLOSED piksel kontrastı, listener'ın hareket etmemesi, konuşma sonrası REST'e dönüş, 24/25/30/60 fps oranlılığı, legacy fallback dürüstlüğü, planner placeholder'larının "ölçüldü" sayılmaması |

Gizlenen/silinen/skip edilen başarısızlık yok. Koşum sırasında çıkan 6 başarısızlığın **tamamı benim test/kod hatalarımdı** ve düzeltildi: `make()` imzası, mikrosaniye yuvarlama, çakışma-vs-clamp karışıklığı, tautolojik cache assertion'ı, `min(*[1.0])` çökmesi, temp dizinin erken silinmesi, `bpy` import eden test, ve `align()`'in availability'yi cache'in önüne koyması.

`test_lipsync_blender_render.py` izole alignment ortamı yoksa **nedeni yazılı** olarak skip olur (`skipif` reason: `tools/alignment-venv` yok). Bu makinede 10/10 koştu; bu durum Bölüm 11'de beyan ediliyor.

---

## 11. BİLİNEN SINIRLAMALAR

1. **Karakter-düzeyi hizalama, fonem-özel model değil.** Akustik model Türkçe **harf** CTC sözlüğüyle eğitimli; zamanlamalar sesin kendisinden ölçülüyor ama IPA fonem sınırında değil. Türkçe ortografisi fonemik olduğu ve brief'in viseme tablosu harf bazlı olduğu için pratik etki düşük; yine de "gerçek fonem modeli" diye sunulmuyor.
2. **Modelin ASR doğruluğu sentetik seste sınırlı.** Greedy transkripsiyon `Merhaba`yı `ner|habahairşey`, `Bugün`ü `bu|gün` olarak okudu; `Çocuklar dışarıda oyun oynuyor` ve `Üç küçük kuş` ise doğru. Forced alignment bilinen transkripti kullandığından bu hata zamanlamaya doğrudan sızmıyor, ancak **anlaşılmaz konuşmada hizalama kalitesi düşer** ve worker o diyaloğu döndürmez (fallback).
3. **Ortalama güven ~0.27.** CTC posterior ortalaması; blank sınıfı baskın olduğundan düşük görünmesi normal. Mutlak "doğruluk" iddiası yok.
4. **Shape key yok, transform var.** Blender'da kanıtlandığı gibi rig'de shape key bulunmuyor; dudak içi detay (diş/dudak teması) FV ve DENTAL'de yalnızca çene+açılma ile ima ediliyor, gerçek diş-dudak mesh'i değil.
5. **Ağır bir izolasyon ortamı gerektiriyor:** ~1.3 GB venv + ~1.3 GB model ağırlığı, ilk hizalamada model yükleme ~2–12 s, diyalog başına ~0.2–0.8 s CPU çıkarım (cache sonrası 0 s). `LIP_SYNC_ENABLED=false` ile tamamen kapatılabilir.
6. **İlk fonem offset'i 0.02 s = bir frame.** Bu, modelin frame çözünürlüğünün (20.1 ms) alt sınırı; daha ince zamanlama bu akustik modelle mümkün değil.
7. **Kuyruk boşluğu 0.27–0.32 s.** Ses dosyalarında konuşma sonrası sessizlik var; ağız son fonemde kapanıyor, sesten "önce" kapanmıyor — doğru davranış, ama `end_time`'ın ses süresiyle birebir eşitlenmesi gerekmiyor.
8. **Sahne geçişinde timeline:** kompozisyon yolu her sahneyi ayrı Blender job'ı olarak render ettiği için diyalog offset'i sahne-yerel kalıyor; crossfade kesişimlerinde iki sahnenin ağız animasyonu üst üste binmez (her klip kendi zaman çizelgesinde).
9. **`SceneCamera.fov` hâlâ kullanılmıyor** (Stage 5.3'te de kapsam dışı bırakılmıştı).
10. **Onaylı API yüzeyi genişletilmedi:** lip-sync durumu yalnızca render metadata üzerinden okunuyor; ayrı bir `/lip-sync/status` endpoint'i bu aşamada eklenmedi.

---

## 12. DEĞİŞEN DOSYALAR, COMMIT VE ÇALIŞMA AĞACI

### Kod — yeni

```
backend/src/tezlify_studio/domain/value_objects/speech_alignment.py
backend/src/tezlify_studio/domain/services/viseme_mapper.py
backend/src/tezlify_studio/domain/services/mouth_poses.py
backend/src/tezlify_studio/application/ports/speech_alignment_port.py
backend/src/tezlify_studio/application/services/lip_sync_resolver.py
backend/src/tezlify_studio/infrastructure/alignment/__init__.py
backend/src/tezlify_studio/infrastructure/alignment/ctc_alignment_worker.py
backend/src/tezlify_studio/infrastructure/alignment/ctc_forced_alignment_impl.py
backend/tests/unit/test_viseme_mapping.py
backend/tests/unit/test_speech_alignment_pipeline.py
backend/tests/integration/test_lipsync_blender_render.py
frontend/src/components/studio/steps/ExportStep.test.ts
scripts/setup_alignment_env.sh
```

### Kod — değiştirilmiş (15 dosya, +540 / −23 satır)

```
backend/src/tezlify_studio/domain/enums/studio_status.py            (+MouthViseme, +AlignmentSource)
backend/src/tezlify_studio/domain/exceptions/studio_exceptions.py    (+3 alignment exception)
backend/src/tezlify_studio/domain/value_objects/scene_graph.py       (DialogueViseme genişletildi)
backend/src/tezlify_studio/domain/value_objects/render_metadata.py   (+lip_sync)
backend/src/tezlify_studio/infrastructure/blender/render_worker.py   (viseme animasyonu, +257)
backend/src/tezlify_studio/infrastructure/blender/blender_animation_engine_impl.py  (lip_sync aktarımı)
backend/src/tezlify_studio/infrastructure/video/ffmpeg_composition_engine.py        (lip_sync agregasyonu)
backend/src/tezlify_studio/infrastructure/configuration/settings.py  (+4 ayar, +4 türetilmiş yol)
backend/src/tezlify_studio/application/use_cases/execute_render_job_use_case.py
backend/src/tezlify_studio/application/use_cases/execute_composition_render_use_case.py
backend/src/tezlify_studio/presentation/dependencies/container.py
frontend/src/components/studio/steps/ExportStep.tsx
frontend/src/types/studio.ts
.env.example   .gitignore
```

### Dokunulmayan (korunan sistemler)

Stage 5.0.1 render cancellation/reconciliation ve graceful shutdown, disk alanı kontrolü, medya path containment, FFprobe medya doğrulaması, ElevenLabs + macOS `say` TTS davranışı, SRT üretimi ve Türkçe karakterler, **Stage 5.3 kamera framing sistemi (16:9 / 9:16 / 1:1 çıktıları)**, crossfade/fade ve ses miksajı, Media Library, YouTube Publisher ve Scheduler — hepsi mevcut testlerle doğrulandı.

### Depo hijyeni

`.gitignore`'a eklendi: `tools/alignment-venv/` (1.3 GB), `tools/hf-cache/` (2.4 GB), `tools/alignment_probe/*.wav`, `data/alignment_cache/`. Bu dizinler commit'e **girmedi**; `scripts/setup_alignment_env.sh` ile yeniden üretilebilir. `.env` (secret) commit'e girmedi. Kullanıcı verisi, veritabanı, sesler ve mevcut render'lar silinmedi; git geçmişi değiştirilmedi; **push ve deploy yapılmadı.**

### Kanıt klasörü

Commit'e girenler (script + ölçüm JSON'u + log, toplam ~0.5 MB):

```
evidence/stage_5_4/render_lipsync_demo.py         ses → alignment → render → fonem kareleri
evidence/stage_5_4/render_composition_av.py       tam zincir, muxed A/V MP4
evidence/stage_5_4/demo/alignment_report.json     4 diyalog, 102 viseme segmenti
evidence/stage_5_4/demo/phoneme_frames.json       24 fonem karesinin zaman çizelgesi
evidence/stage_5_4/demo/viseme_contrast.json      OPEN↔CLOSED piksel kontrastı
evidence/stage_5_4/demo/sync_measurements.json    ses/animasyon senkron ölçümleri
evidence/stage_5_4/demo/render_probe.json         ffprobe
evidence/stage_5_4/demo/render_lip_sync_report.json  worker'ın kendi lip-sync raporu
evidence/stage_5_4/composition_av/av_evidence.json   A/V zincir kanıtı
evidence/stage_5_4/viseme_poses/pose_geometry.json  10 pozun world bbox'ı
evidence/stage_5_4/evidence_run.log  regression.log
tools/alignment_probe/probe_ctc.py + sentences.json + ctc_probe_result.json
```

Diskte kalan, commit'e **alınmayan** görseller (45 PNG, ~52 MB — Stage 5.3'te uygulanan aynı
kural: git geçmişine binary yığını koymamak; önceki aşamaların `evidence/` klasörleri de
track edilmedi):

```
evidence/stage_5_4/mouth_axes/*.png       eksen keşfi kareleri (ölçüm gerekçesi)
evidence/stage_5_4/viseme_poses/*.png     10 poz karesi + pose_contact_sheet.png
evidence/stage_5_4/demo/ali_*.png         24 fonem karesi + phoneme_contact_sheet.png
evidence/stage_5_4/composition_av/*.png   4 A/V karesi
```

Bu PNG'ler iki script ile her an yeniden üretilebilir; ölçümleri ve yolları JSON'larda ve bu
raporda sabittir. İstenirse kanıt görselleri ayrıca stage'lenebilir.

### Commit

```
da1dc64  feat(studio): implement phoneme-based character lip sync
```

Kod, testler ve hafif kanıt artefaktları bu tek commit'te yer aldı. Ardından yalnızca bu
rapordaki SHA alanı dolduruldu (`docs(studio): record Stage 5.4 commit SHA`) — Bölüm 1'de
açıklandığı için ayrılmaz bir sıralı düzeltmedir. Push ve deploy yapılmadı.

---

## 13. SONUÇ

**PASS**

Brief'in PASS kriteri üç koşul istiyordu; üçü de ölçüldü:

1. **Gerçek Türkçe ses üzerinde gerçek fonem/viseme zamanlaması elde edildi.**
   Yerel CTC forced alignment, `Baybars/wav2vec2-xls-r-300m-cv8-turkish` (Apache-2.0, gated değil), macOS `say`/Yelda tr_TR sesleri üzerinde 4/4 diyalog, 102 segment. Zamanlamalar metin uzunluğundan türetilmedi: kelime aralıkları gerçek duraklamalara denk geliyor ve segment süreleri eşit değil.

2. **Blender karakter ağız animasyonu bu zamanlamayı takip etti.**
   Keyframe'ler aligner'ın ürettiği karelerle birebir eşleşiyor (24/25/30/60 fps'nin hepsinde test edildi), yalnızca konuşan karakter animasyonlanıyor, dinleyici rest'te kalıyor, konuşma bitince ağız kapanıyor (0.081 m → 0.042 m).

3. **Gerçek render karelerinde doğrulandı.**
   OPEN↔CLOSED ağız bölgesi piksel farkı %37–70, koyuluk oranı 3.2×; `phoneme_contact_sheet.png` ve 24 fonem karesi görsel kanıt; tam üretim zincirinin sonunda AAC'li 9:16 MP4'te `real_lip_sync: True`.

Ayrıca: tahmini zamanlama veya eski ritmik çırpma PASS olarak sunulmadı — fallback durumları `estimated` / `legacy_flap` etiketiyle ayrıştırılıyor ve UI'da "Gerçek lip-sync" olarak görünemiyor. MFA'nın bu makinede kurulamadığı ve ElevenLabs anahtarının bulunmadığı negatif sonuçlar raporlandığı gibi bırakıldı.
