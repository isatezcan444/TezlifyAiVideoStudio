# STAGE 5.3 — TRUE VERTICAL VIDEO COMPOSITION & SMART CAMERA FRAMING

**Proje:** Tezlify AI Video Studio
**Aşama:** Stage 5.3 — Gerçek Dikey Video Kompozisyonu ve Akıllı Kamera Kadrajı
**Tür:** Kodlama
**Branch:** `main`
**Başlangıç commit'i:** `b25aaeafe6e3fab1d9f53578bfcd3d321d58b391` (Stage 5.2.1 — `fix(studio): verify character quality and resolve test regressions`)
**Rapor tarihi:** 2026-11-04
**Ortam:** Blender 5.2.3 LTS · FFmpeg 9.0.2 · Python 3.14.7 · macOS (Darwin 27.0.0, arm64)

---

## 0. ÖZET VE EN KRİTİK BULGU

Stage 5.3'te hedef, 9:16 çıktısında "siyah letterbox" şikâyetini çözmekti. Mimari inceleme ve
**gerçek piksel ölçümü** şu sonucu verdi:

> **Sahte siyah letterbox bandı, başlangıç commit'inde (b25aaea) artık mevcut değildi.**
> Hem mevcut production 9:16 render'larında hem de bu aşamada HEAD koduyla yeniden üretilen
> karelerde kenar siyah bandı oranı **0.000** ölçüldü. Bununla birlikte şikâyetin gerçek
> kaynağı devam ediyordu: **dikey kadraj, yatay kadrajın uzantısıydı.** Karakterler ekranın
> orta bandında küçük kalıyor, üstte boş duvar, altta boş zemin birikiyor ve altyazı kutusu
> karakterlerin bacaklarının üzerine biniyordu.

Bu nedenle çözüm FFmpeg filtrelerinde değil **kamera çözümlemesinde** yapıldı. Aşamanın
temel ölçüsü:

| Metrik (9:16, iki karakter) | Önce (b25aaea sabit rig) | Sonra (Stage 5.3) |
|---|---|---|
| Öznenin ekran yüksekliği payı | **0.313** | **0.625** |
| Güvenli bant doluluğu (yükseklik) | **0.441** | **0.880** |
| Gövde altındaki ölü alan | 0.331 | 0.243 (altyazı/UI bandı) |
| Siyah kenar bandı | 0.000 | 0.000 |
| Güvenli alan ihlali | yok | yok |

16:9'da ise tam tersi bir kusur düzeltildi: eski sabit rig'de özne ekran yüksekliğinin
**0.980**'ini kaplıyor, gövde alt kenurdan taşıyordu (`dead_space_below_body = -0.014`) ve
**güvenli alan ihlali** vardı. Stage 5.3 sonrası 16:9 **0.799** dolulukla güvenli alan içinde.

Üç formatın tamamı gerçek Blender + FFmpeg render'ı ile üretildi, görsel olarak doğrulandı ve
FFprobe ile ölçüldü.

---

## 1. BAŞLANGIÇ VE BİTİŞ COMMIT SHA

| | Değer |
|---|---|
| Başlangıç (Stage 5.2.1 HEAD) | `b25aaeafe6e3fab1d9f53578bfcd3d321d58b391` |
| Branch | `main` (doğrulandı: `git branch --show-current`) |
| Stage 5.3 implementasyon commit'i | `e9f4c78` — `feat(studio): implement true vertical video composition` (18 dosya, +4787 / −94) |
| Bitiş (bu commit) | `docs(studio): record Stage 5.3 commit SHA` — rapor, SHA'sı bilinen tek dosyadır; bu satır o yüzden ayrı bir docs commit'i olarak güncellenmiştir |

---

## 2. MİMARİ İNCELEME — MEVCUT SİSTEMDE 5 SORUNUN CEVABI

İnceleme, brief'in istediği beş sorunun cevabını netleştirdi:

1. **Blender hangi çözünürlükte render alıyor?**
   Kompozisyon yolunda **hedef formatın kendi çözünürlüğünde.**
   `ffmpeg_composition_engine.py` her sahneyi render etmeden önce `SceneResolution`'ı
   kompozisyonun `width/height/format` değerleriyle eziyor
   ([ffmpeg_composition_engine.py:157](backend/src/tezlify_studio/infrastructure/video/ffmpeg_composition_engine.py)
   civarı, `single_graph.resolution = SceneResolution(...)`); worker da bu değeri doğrudan
   `scene.render.resolution_x/y` olarak uyguluyor. Yani 9:16 için 1080×1920 **Blender'da**
   üretiliyor, FFmpeg'de ölçeklenmiyor.

2. **Composition aşamasında format değişikliği nasıl uygulanıyor?**
   `VideoComposition.normalize_and_validate()` teslim formatını yetkili kılıyor ve
   `width/height`'ı `FORMAT_DIMENSIONS`'tan yeniden türetiyor
   ([video_composition.py:163](backend/src/tezlify_studio/domain/value_objects/video_composition.py)).
   Frontend de aynı tabloyu kullanıyor, yani iki tarafta da tek doğruluk kaynağı `format`.

3. **16:9 ve 9:16 aynı kaynak videodan mı üretiliyor?**
   **Hayır — ve bu önemliydi.** Her format için sahneler Blender'da o formata özel yeniden
   render ediliyor. Dolayısıyla sorun "yanlış kaynak" değil, **her format için aynı kamera
   kurallarının kullanılmasıydı.**

4. **Kamera, karakter koordinatları ve sahne sınırları nerede tanımlı?**
   - Kamera: `render_worker.py` içindeki `get_camera_positions(angle, aspect_ratio)` — açı
     başına **sabit** konum/hedef/lens; 9:16 için yalnızca `lens *= 1.05` ve mesafe `*1.04`
     gibi sezgisel bir zoom.
   - Karakter koordinatları: `StudioScene.character_placements[].position` (world X/Y/Z).
   - Sahne sınırları: `blender_scene_asset_builder.py` — café duvarı `scale=(10, 0.2, 5)`
     yani z ∈ [0, 5], zemin 10×10 plane.
   - **Kritik geometri:** worker `sensor_fit = 'HORIZONTAL'` kullanıyor. Yatay FOV lens ile
     sabit; dikey FOV çerçeve oranını takip ediyor. 9:16'da aynı lens **~3.16 kat daha fazla
     dikey dünya** gösterir. Üstte duvarın bittiği yerin ötesi siyah world background'dur.
     Eski kod bunu 2.4× sabit duvar büyütmesi ile tahmin ediyordu.

5. **Karakter kadraj dışına çıkıyor mu, nasıl tespit edilir?**
   Ölçülebilir tek yol: rig'in **world-space bounding box**'ını alıp kamera matrisiyle ekran
   koordinatına izdüşürmek. Stage 5.3 bunu kalıcı hâle getirdi; worker artık her sahne için
   `render_result.json` içine `framing` raporu yazıyor (karakter başına normalize ekran kutusu).

**Karar:** Sahneyi hedef en-boy oranında Blender ile **yeniden kadrajlayarak** render etmek.
FFmpeg crop tek başına reddedildi çünkü kaynak zaten dikey çözünürlükte üretiliyordu; crop
yalnızca mevcut kadrajı küçültür, kötü kadrajı düzeltemez. Brief'in "karakterleri kesen basit
merkez crop yeterli değil" uyarısı bu kararı doğruluyor.

---

## 3. ESKİ VE YENİ KADRAJ MİMARİSİ

### 3.1 Önce

```
VideoComposition.format ──> SceneResolution(w,h,aspect) ──> Blender
                                                            │
                                     get_camera_positions(angle, aspect)
                                     │  açı başına SABIT lens/mesafe
                                     │  9:16 → lens*1.05, y*1.04 (sezgisel)
                                     │  Cafe_BackWall.scale.z *= 2.4 (sezgisel)
                                     ▼
                            sensor_fit=HORIZONTAL → dikey FOV 3.16 kat artar
                                     ▼
                        üstte boş duvar + altta boş zemin + küçük özne
```

FFmpeg tarafında ayrıca `scale=…force_original_aspect_ratio=decrease` + `pad=…color=black`
("contain") zinciri vardı. Bu zincir hedef ölçü tuttuğunda etkisizdi; tutmadığında ise
**siyah bant üretmeye programlıydı.**

### 3.2 Sonra

```
VideoComposition.format
   └─> SceneResolution(w,h,aspect)
          └─> FramingProfile (landscape / portrait / square)      ← YENİ domain katmanı
                 • hedef çözünürlük + kamera aspect
                 • platform güvenli alanı (üst/alt/sol/sag inset)
                 • subject_fill (nefes payı)
                 • horizontal_spacing_ratio (dikeyde cast'i yaklaştırma)
                 • body_crop_adjust (dikeyde gövdeyi açma)
                 • rig min/max mesafe ve min lens
                      │
   Blender worker     ▼
   1. Placement x'leri grup merkezine göre ölçekle (dar kadraj için)
   2. Rig'i oturt, pose/animasyon keyframe'lerini at
   3. world-space bbox ÖLÇ (sahnenin baş/orta/son karesinde)
   4. solve_camera(profile, bounds, intent) → lens + mesafe + aim (kapalı form)
   5. lens/target/kamera keyframe'lerini çözülmiş değerlerle yaz
   6. Görünür dünya dikdörtgenini hesapla → seti (duvar/zemin) bu alanı kaplayacak büyüt
   7. framing raporunu yaz (karakter başına ekran kutusu)
```

Kamera artık formatın **fonksiyonu**, sabit bir tablo değil. Ölçüm animasyon üzerinden
yapıldığı için jest sırasında kalkan kol ya da otururken alçalan baş kadraj hesabına giriyor.

---

## 4. 9:16 SORUNUNUN ÇÖZÜMÜ

### 4.1 Dikey kadraj neden boşlukla doluyordu

`sensor_fit = 'HORIZONTAL'` ile 45 mm lens, 36 mm sensörde yatay FOV'u sabitler. Aynı lens
1080×1920'de dikey FOV'u 16:9'a göre 3.16 katına çıkarır. Eski kod bunu yalnızca %5 zoom ile
telafi etmeye çalıştı; sonuçta kamera **geriye** gitmesi gerekirken neredeyse hiç
gitmediğinden özne çerçevenin küçük bir bandında kaldı.

### 4.2 Çözüm: kapalı form çözümleme

`camera_framing.py:313` `solve_camera`:

```
k               = (sensor_width_mm / 2) / lens
visible_width   = 2 · distance · k
visible_height  = visible_width · (height_px / width_px)

d_w = subject_width  / (2·k·safe_w·fill)
d_h = subject_height / (2·k·safe_h·fill·(H/W))
distance = clamp(max(d_w, d_h), min_distance, max_distance)
```

Rig geriye gidemiyorsa lens açılır (`min_lens`'e kadar); o da yetmiyorsa `fits=False`
raporlanır ve worker log'a WARNING yazar — **sessizce kırpmaz.**

Dikeyde iki hamle daha var:
- `horizontal_spacing_ratio = 0.66`: yan yana iki karakter grup merkezine doğru çekilir.
  Dikey çerçevenin genişliği dardır; karakterleri yaklaştırmak, kameranın içeri girmesini
  sağlar. Yatayda oran **1.0** — mevcut blocking'e dokunulmaz.
- `body_crop_adjust = 1.14`: dikeyde kadraj bel/omuz yerine dize kadar açılır; kazanılan
  yükseklik karaktere harcanır, duvara değil.

### 4.3 Ölçülen sonuç (gerçek render raporu, `solve_final/framing_report.json`)

| Format | Profil | lens | mesafe | visW | visH | subjW | subjH | sınırlayan | fits |
|---|---|---|---|---|---|---|---|---|---|
| 16:9 | landscape | 45.0 mm | 3.952 m | 3.161 | 1.778 | 1.719 | 1.421 | height | ✔ |
| **9:16** | **portrait** | **45.0 mm** | **2.076 m** | **1.661** | **2.953** | **1.345** | **1.620** | **width** | ✔ |
| 1:1 | square | 45.0 mm | 2.632 m | 2.106 | 2.106 | 1.543 | 1.492 | height | ✔ |

Karakter başına ekran kutuları (0 = kenar, normalize):

| Format | Ali x / y | Ayşe x / y | Yorum |
|---|---|---|---|
| 16:9 | x[0.228, 0.424] y[0.082, 0.872] | x[0.544, 0.772] y[0.075, 0.875] | Başlar üstte, gövde altta; güvenli alan içinde |
| **9:16** | x[0.095, 0.468] y[0.175, 0.717] | x[0.472, 0.905] y[0.171, 0.719] | İki yüz de net, baş kesilmemiş, alt %20 altyazı bandı boş |
| 1:1 | x[0.134, 0.428] y[0.106, 0.807] | x[0.525, 0.866] y[0.101, 0.809] | Denge |

Hiçbir karakter kutusu [0,1] aralığının dışına taşmıyor; 9:16'da üst güvenli inset 0.09 ve
başlar 0.17'de, alt inset 0.20 ve gövde bitişi 0.72'de.

---

## 5. BLENDER VE FFMPEG TARAFINDAKİ DEĞİŞİKLİKLER

### 5.1 Yeni dosya — `backend/src/tezlify_studio/domain/value_objects/camera_framing.py`

Saf standart kütüphane (pydantic yok) — Blender'ın gömülü Python'u pydantic taşımıyor ve bu
modülü doğrudan import ediyor. İçerik: `SafeArea`, `FramingProfile` (+ `LANDSCAPE` /
`PORTRAIT` / `SQUARE`), `ShotIntent` (açı → lens / yükseklik ofseti / body crop),
`SubjectBounds`, `FramingSolve`, `solve_camera`, `screen_box`,
`visible_extents_at_plane`, `profile_for_aspect`, `profile_for_dimensions`.

Format profilleri:

| Profil | Çözünürlük | Kamera aspect | Güvenli alan (üst/alt/sol/sağ) | subject_fill | spacing | crop adjust |
|---|---|---|---|---|---|---|
| landscape | 1920×1080 | 16:9 | 0.05 / 0.10 / 0.03 / 0.03 | 0.94 | 1.00 | 1.00 |
| portrait | 1080×1920 | 9:16 | 0.09 / 0.20 / 0.04 / 0.04 | 0.88 | 0.66 | 1.14 |
| square | 1080×1080 | 1:1 | 0.07 / 0.16 / 0.04 / 0.04 | 0.92 | 0.84 | 1.05 |

Güvenli alanlar TikTok/Reels/Shorts arayüzü (alt sağ kontroller, alt yazı alanı, üst durum
çubuğu) referans alınarak seçildi; alt inset her formatta en büyük değer — altyazı oraya
düşüyor.

### 5.2 `render_worker.py`

- `get_camera_positions()` **kaldırıldı** (sabit açı→kamera tablosu ve sezgisel 9:16 zoom'u).
- `Cafe_BackWall.scale.z *= 2.4` **kaldırıldı**; yerine ölçüm tabanlı
  `expand_backdrop_for_frame()` geldi ([render_worker.py:185](backend/src/tezlify_studio/infrastructure/blender/render_worker.py)).
  Artık duvar/zemin, kameranın o düzlemde **gerçekten gördüğü** dikdörtgeni kapsayacak şekilde
  büyüyor; isim kalıbı ile tüm preset'lerde çalışıyor (café, office, living room, park,
  tech studio). 16:9'da gerekli kapsama zaten duvarın içinde olduğundan set hiç oynamıyor —
  regression riski yok.
- `object_world_bounds` / `measure_subject_bounds` ([render_worker.py:92](backend/src/tezlify_studio/infrastructure/blender/render_worker.py),
  [:120](backend/src/tezlify_studio/infrastructure/blender/render_worker.py)):
  her sahnenin baş/orta/son karesinde `frame_set` + `view_layer.update()` ile rig'lerin
  world-space bbox'ı ölçülüyor.
- Kamera çözümü sahne döngüsünün **sonuna** taşındı
  ([render_worker.py:661](backend/src/tezlify_studio/infrastructure/blender/render_worker.py)),
  böylece diyalog jestleri de ölçüme giriyor.
- `lens`, `cam_target.location` ve `cam_obj.location` artık sahne **baş + son** karesinde
  keyframe'leniyor. Eski kod hedefi ve lensi keyframe'siz atıyordu; çok sahneli project
  render'larda son sahnenin hedefi tüm kareye sızıyordu. Bu, yol açtığım riski de kapattı.
- Pan/dolly genlikleri çözülmiş kadraja göre ölçekleniyor (`pan ∝ visible_width`,
  `dolly ∝ distance`), böylece kamera hareketleri dar dikey kadrajda özneyi dışarı atmıyor;
  animasyon hareketlerinin kendisi korunuyor.
- `render_result.json` içine `framing` bloğu yazılıyor
  ([render_worker.py:860](backend/src/tezlify_studio/infrastructure/blender/render_worker.py)):
  profil, güvenli alan, sahne başına solve ve karakter başına ekran kutusu.
- Boyut ile aspect çelişirse **piksel boyutu kazanır** ve WARNING düşer (eski proje
  render'ları için koruyucu).

### 5.3 `ffmpeg_composition_engine.py`

- `scale=…decrease` + `pad=…color=black` zinciri **kaldırıldı.** Yerine
  `build_cover_fit_filter()` ([ffmpeg_composition_engine.py:60](backend/src/tezlify_studio/infrastructure/video/ffmpeg_composition_engine.py)):
  - Ölçüler tutuyorsa **filtre yok** (passthrough) — yeniden örnekleme de yok.
  - Tutmuyorsa `scale=<fill, force_original_aspect_ratio=disable>` + `crop=W:H:x:y`,
    **pad yok**. Siyah bant üreten hiçbir dal kalmadı.
  - Crop penceresi geometrik merkeze değil, **kaynak formatın güvenli merkezine**
    yerleştiriliyor; dikey klip yataya çevrilirken zemin değil yüzler kalıyor.
- Her sahne klibi kompozisyondan önce FFprobe ile ölçülüyor
  (`_probe_clip_geometry`, [:728](backend/src/tezlify_studio/infrastructure/video/ffmpeg_composition_engine.py));
  width/height/pix_fmt/codec/SAR/DAR `composition_manifest.json` içinde
  `scene_clip_probe` olarak saklanıyor ([:395](backend/src/tezlify_studio/infrastructure/video/ffmpeg_composition_engine.py)).
- Filtre sırası: `fps → (cover scale → crop) → setsar=1 → format=yuv420p → setpts → fade`.
- Ses, geçişler, sahne sırası, süre, overlay konumları ve hata yönetimi
  (`CompositionRenderException`) **değiştirilmedi.**

### 5.4 Frontend

**Kod değişikliği gerekmedi.** `CompositionStudioPage.tsx:504` zaten
*"Format değiştiğinde kamera çerçevesi ve güvenli metin alanları otomatik uyarlanır."*
diyordu ve format seçenekleri çözünürlükleri gösteriyordu (1920×1080 / 1080×1920 / 1080×1080).
Stage 5.2.1'de bu metin Backend tarafından karşılanmıyordu; Stage 5.3 ile **iddia gerçeğe
dönüştü.** Tasarımı gereksiz değiştirmemek için arayüze dokunulmadı.

---

## 6. ALİ / AYŞE GÖRSEL KARŞILAŞTIRMALARI

Tüm görseller `evidence/stage_5_3/` altında.

### 6.1 Önce (HEAD `b25aaea`, kod değişmeden önce ölçüldü)

| Kanıt | Ne gösteriyor |
|---|---|
| `baseline/9x16_t00.55s.png` | Dikey kare: iki karakter ekranın orta bandında küçük; üstte ~%40 boş duvar, altta ~%20 boş zemin. Siyah bant yok ama **ölü alan** var. |
| `baseline/16x9_t00.55s.png` | Yatay kadraj çok sıkı: başlar üst kenara değiyor, gövdeler alt kenurdan taşıyor. |
| `baseline_final/comp_fc2d5d972c7d_t1.png` | Gerçek production 9:16 çıktısı (Stage 5.2.1 sonrası). Altyazı kutusu karakterlerin **bacaklarının üstüne** biniyor; başlık rafı kesiyor. |
| `baseline_final/job_20261104_131723_9x16_t1.png` | Bir önceki demo 9:16 çıktısı — aynı ölü alan deseni. |

### 6.2 Sonra (nihai kodla üretilen gerçek kompozisyon render'ları)

| Kanıt | Ne gösteriyor |
|---|---|
| `final/9x16/scene_01_opening_t01.440s.png` | Dikey açılış: iki karakter kadrajı dolduruyor, yüzler net. |
| `final/9x16/scene_02_dialogue_t07.940s.png` | Dikey diyalog (oturur poz): başlar y≈0.17, gövdeler y≈0.72'de bitiyor; altta altyazı bandı temiz. |
| `final/9x16/subtitle_t05.000s.png` | **Kilit kare:** Türkçe altyazı ("Merhaba Ayşe, bugün nasılsın? Kafeye gelirken seni düşündüm.") tamamen alt güvenli bantta; hiçbir yüzü, başı veya gövdeyi örtmüyor. |
| `final/9x16/scene_03_closing_t15.307s.png` | Kapanış kadrajı da dolu. |
| `final/16x9/*.png` | Yatay kalite korunmuş; başlar artık üst kenara değmiyor. |
| `final/1x1/*.png` | Kare kadraj dengeli, iki karakter de tam. |
| `final/contact_sheet.png` | **Yan yana karşılaştırma:** 3 satır (3 zaman damgası) × 3 sütun (16:9 / 9:16 / 1:1), aynı anların üç formatı. |
| `solve_final/{16x9,9x16,1x1}_t00.55s.png` | Blender-only kadraj doğrulaması (kompozisyon katmanı hariç). |

### 6.3 9:16 için istenen kriterlerin tek tek karşılığı

| Kriter | Durum | Kanıt |
|---|---|---|
| Siyah letterbox yok | ✔ | 9 karede kenar bandı 0.000 (`final/evidence.json`) |
| İki karakterin de yüzü görünmeli | ✔ | Ekran kutuları x[0.095,0.468] ve x[0.472,0.905]; `final/9x16/subtitle_t05.000s.png` |
| Baş/gövde gereksiz kesilmemeli | ✔ | y_top 0.17 ≥ güvenli üst 0.09; y_bottom 0.72 ≤ 0.80 |
| Dikey ekranı dengeli kullanmalı | ✔ | Özne yükseklik payı 0.313 → **0.625**; güvenli bant doluluğu **0.880** |
| Altyazılar güvenli alanda | ✔ | Varsayılan margin 0.075 → y 0.925; özne 0.72'de bitiyor, çakışma yok (görselde doğrulandı) |
| Bulanık / aşırı zoom yok | ✔ | Lens 45 mm (portre için normal); mesafe 2.08 m; pix_fmt yuv420p, CRF 20 korunuyor |
| Tek sabit kare değil, ≥3 zaman damgası | ✔ | Her format için 3 sahne ortası + 1 altyazı anı = 4 kare |

---

## 7. ÜÇ FORMAT İÇİN GERÇEK RENDER DOSYA YOLLARI

Aynı sahne seti (Ali & Ayşe, 3 sahne, 2 crossfade + fade-out, Türkçe altyazı + 3 metin katmanı,
AAC ses) tek `SceneGraph`'tan üretildi. Job damgası: `20261104_232448`.

```
data/studio_projects/demo_stage_4_5/renders/job_20261104_232448_16x9/job_20261104_232448_16x9.mp4
data/studio_projects/demo_stage_4_5/renders/job_20261104_232448_9x16/job_20261104_232448_9x16.mp4
data/studio_projects/demo_stage_4_5/renders/job_20261104_232448_1x1/job_20261104_232448_1x1.mp4
```

Yan dosyalar (her job klasöründe): `subtitles.srt`, `render_metadata.json`.
Kompozisyon manifestleri: `data/studio_projects/demo_stage_4_5/compositions/<job>/composition_manifest.json`.

> Not: `*.mp4` ve `data/studio_projects/` `.gitignore`'da; videolar yerel kanıt olarak
> diskte duruyor, ölçüm çıktıları ve PNG kareler `evidence/stage_5_3/` altında commit edildi.

**Ses kaynağı dürüstlüğü:** `ELEVENLABS_API_KEY` tanımlı değil; diyaloglar macOS `say` /
**Yelda (tr_TR)** fallback ile üretildi (`voice_source: macos_say`). Bu çıktı ElevenLabs
çıktısı olarak raporlanmıyor.

---

## 8. FFPROBE SONUÇLARI

| Alan | 16:9 | 9:16 | 1:1 | Beklenen |
|---|---|---|---|---|
| width × height | 1920 × 1080 | 1080 × 1920 | 1080 × 1080 | ✔ üçü de |
| display_aspect_ratio | 16:9 | 9:16 | 1:1 | ✔ |
| sample_aspect_ratio | 1:1 | 1:1 | 1:1 | ✔ (SAR 1 → anamorfik yok) |
| codec_name (video) | h264 | h264 | h264 | ✔ |
| pix_fmt | yuv420p | yuv420p | yuv420p | ✔ |
| avg_frame_rate | 30/1 | 30/1 | 30/1 | ✔ |
| duration | 17.067 s | 17.067 s | 17.067 s | ✔ üçü de eşit |
| video stream | var | var | var | ✔ |
| audio stream | var | var | var | ✔ |
| audio codec / sr / ch | aac / 44100 / 2 | aac / 44100 / 2 | aac / 44100 / 2 | ✔ |
| dosya boyutu | 2 095 539 B | 1 641 224 B | 1 349 506 B | — |
| SRT cue / metin katmanı / geçiş / sahne | 2 / 3 / 2 / 3 | 2 / 3 / 2 / 3 | 2 / 3 / 2 / 3 | ✔ |

Her format için `validate_output` kontrolleri: `video_stream, audio_stream, h264, aac, width,
height, duration, subtitles` → **hepsi true**; ayrıca tam decode pası
(`ffmpeg -v error -f null`) hatasız geçti.

Ham JSON: `evidence/stage_5_3/final/evidence.json`.

---

## 9. SİYAH PADDING VE KARAKTER KESİLMESİ KONTROLLERİ

### 9.1 Siyah padding

Ölçüm yöntemi (`evidence/stage_5_3/measure.py`): kenara bitişik, **tamamen** karesi
maksimum kanalı < 14 olan satır/sütun koşusu. Koyu ama dolu sahne bant sayılmıyor.

| Küme | Kare sayısı | En kötü kenar bandı |
|---|---|---|
| `final/` (16:9 + 9:16 + 1:1, 3'er sahne karesi) | 9 | **0.000** |
| `solve_final/` (Blender-only, 3 format × 3 zaman) | 9 | **0.000** |

Global siyah piksel oranı da tüm karelerde **0.0000**.

### 9.2 Karakter kesilmesi

İki bağımsız doğrulama:

1. **Analitik:** worker'ın yazdığı `screen_box` değerleri; `x0 ≥ 0`, `x1 ≤ 1`,
   `y_top ≥ 0`, `y_bottom ≤ 1` ve `y_top ≥ safe.top − 0.05`. 3 format × 2 karakter için
   sağlanıyor ve `test_blender_animation_render.py` bunu **gerçek render** üzerinde kilitliyor.
2. **Piksel:** kenar bandı ölçümü, kadraj dışına taşan bir öznenin yaratacağı siyah/sert
   kenar izini yakalar.

### 9.3 Otomatik testler (kalıcı hâle getirildi)

| Test | Ne kanıtlıyor |
|---|---|
| `test_camera_framing.py` (34 test) | Profil kaydı, çözüm matematiği, güvenli alan, spacing/crop, lens fallback, rig limiti, determinizm, backdrop kapsaması |
| `test_real_blender_render_frames_the_cast_for_every_delivery_format` (3 parametre) | Gerçek Blender render'ında **hem** siyah bandın 0.000'ı **hem** ekran kutularının güvenli alanda olması |
| `test_portrait_camera_reframes_for_different_character_positions` (3 parametre) | Tek konuşmacı / oturur ikili / geniş ayrılmış cast — üçü de 9:16'da kesilmeden kadrajlanıyor |
| `test_portrait_and_landscape_solves_reach_different_distances_for_the_same_shot` | Aynı blocking iki formatta **aynı kamerayı kullanmıyor** (format kamerayı sürüyor) |
| `test_mismatched_scene_clips_are_filled_not_letterboxed` (3 parametre) | 16:9 klip → 9:16/16:9/1:1 hedefte çıktı tam dolu, kenar bandı 0.000 |
| `test_cover_fit_filter_*` (4 test) | `pad=` yok, crop kaynak güvenli merkezine konumlanıyor, ölçü tutunca passthrough, okunamayan klip hata veriyor |
| `test_composition_manifest_records_the_measured_clip_geometry` | FFprobe ile ölçülen klip geometrisi manifeste yazılıyor |

---

## 10. EK TEKNİK DOĞRULAMALAR (Brief Bölüm 8)

| Kontrol | Sonuç | Nerede |
|---|---|---|
| Crossfade geçişi | ✔ | `test_composition_engine_keeps_audio_continuous_across_crossfade`, demo render (2 geçiş) |
| Fade-in / fade-out | ✔ | `test_last_scene_fade_out_is_kept`, `test_cut_and_fade_transitions_do_not_shorten_timeline` |
| Türkçe altyazı | ✔ | `test_text_overlay_supports_turkish_glyphs_and_transparency`, `test_subtitle_timing_uses_measured_audio_duration`, `final/9x16/subtitle_t05.000s.png` |
| Ses senkronizasyonu | ✔ | crossfade testi (ilk konuşma 0.40 s ≈ beklenen) + 3 formatın süresi eşit (17.067 s) |
| Birden fazla sahnenin birleştirilmesi | ✔ | 3 sahneli demo, üç formatın tamamı |
| Farklı karakter pozisyonları | ✔ | yeni parametrik test (single / sitting / wide) |
| Eski projelerin yeniden render'ı | ✔ | boyut↔aspect çelişkisinde piksel boyutu yetkili + WARNING; `profile_for_dimensions` fallback; 223 testin tamamı eski şemalarla geçiyor |
| Render iptali ve hata yönetimi | ✔ | `test_cancel_pending_render_job`, `test_cancel_completed_render_job_is_noop`, `test_cancel_nonexistent_job_returns_404`, `test_composition_engine_reports_failing_scene_and_can_retry` — kod yollarına dokunulmadı |
| FFprobe ile oran/çözünürlük/piksel formatı doğrulaması | ✔ | klip-öncesi `_probe_clip_geometry` + nihai çıktı doğrulaması |

---

## 11. REGRESYON SONUÇLARI

Tamamı **nihai kodla**, eşzamanlı dosya değişikliği olmadan koştu (ilk koşuda 2 test
bulgusu çıktı, düzeltildi ve suite baştan koştu).

| Koşu | Komut | Sonuç |
|---|---|---|
| Backend | `PYTHONPATH=backend/src .venv/bin/python -m pytest backend/tests -q` | **223 passed**, 1 warning (zaten var olan Starlette `httpx` deprecation uyarısı), 80.67 s |
| Frontend unit | `npm run test` (vitest) | **23 passed** / 4 dosya (composition.test, VideoLibraryPage, CompositionStudioPage, StudioWorkspacePage) |
| Production build | `npm run build` (`tsc && vite build`) | ✔ 1547 modül, 1.54 s, hatasız |
| Sistem denetimi | `scripts/doctor.py` | ✔ Python 3.14.7, Node v24.15.0, npm 11.12.1, FFmpeg/FFprobe, Blender mevcut, medya dizini ve SQLite OK |
| Uçtan uca | `scripts/verify_e2e.py` | ✔ 10 adım tamam (health, system status, import+SHA-256, katalog, HTTP 206 range, 409 duplicate, kalıcılık, güvenli silme, YouTube endpoint'leri, scheduler) |

**Başarısız test gizlenmedi, skip eklenmedi.** İlk full koşuda çıkan 2 başarısızlık bu
aşamada **benim eklediğim** testlerdi ve ikisi de gerçek bulguydu:

1. Yerleştirilmemiş bir rig sahne üzerinde durmaya devam ettiği için kadraj ölçümüne
   giriyordu (mevcut ürün davranışı). Test beklentisi yanlıştı; rapor artık `placed`
   (yazarın blocking'i) ve `cast` (ölçülen rig'ler) alanlarını ayırıyor.
2. Dikeyde karakterlerin **ekran üzerinde** daha geniş ayrıldığı ölçüldü; daralma **dünya
   uzayında**. Test yanlış iddiayı denetliyordu; artık `subject_width_m` ve `fill_width`
   üzerinden doğru iddiayı denetliyor.

Korunan sistemler (değişmedi, suite'te doğrulandı): Stage 5.0.1 render
cancellation/reconciliation, graceful shutdown, disk alanı kontrolü, medya path containment,
FFprobe medya doğrulaması, ElevenLabs + macOS `say` fallback, SRT üretimi ve Türkçe karakterler,
render history ve Media Library, YouTube Publisher ve Scheduler.

---

## 12. DEĞİŞEN DOSYALAR, COMMIT VE ÇALIŞMA AĞACI

### Kod (Stage 5.3 kapsamı)

```
A  backend/src/tezlify_studio/domain/value_objects/camera_framing.py          (yeni)
M  backend/src/tezlify_studio/infrastructure/blender/render_worker.py
M  backend/src/tezlify_studio/infrastructure/video/ffmpeg_composition_engine.py
A  backend/tests/unit/test_camera_framing.py                                   (yeni)
M  backend/tests/integration/test_blender_animation_render.py
M  backend/tests/integration/test_video_composition_engine.py
```

Diff büyüklüğü: 4 izlenen dosyada +1037 / −94 satır; ayrıca 2 yeni Python dosyası.

### Kanıt

Commit'e girenler (≈100 KB, metrik ve script):

```
A  evidence/stage_5_3/measure.py
A  evidence/stage_5_3/probe_formats.py
A  evidence/stage_5_3/collect_evidence.py
A  evidence/stage_5_3/compare_before_after.py
A  evidence/stage_5_3/before_after_framing.json
A  evidence/stage_5_3/solve_final/framing_report.json
A  evidence/stage_5_3/solve_final/probe_report.json
A  evidence/stage_5_3/baseline/probe_report.json
A  evidence/stage_5_3/final/evidence.json
A  evidence/stage_5_3/regression.log
A  evidence/stage_5_3/final_measurement.log
A  STAGE_5_3_VERTICAL_COMPOSITION_REPORT.md
```

Diskte kalan, commit'e **alınmayan** görseller (33 PNG, 35 MB — git geçmişine binary yığını
koymamak için; önceki aşamaların `evidence/` klasörleri de track edilmedi):

```
evidence/stage_5_3/baseline/**            (ÖNCE — Blender-only, b25aaea kodu ile)
evidence/stage_5_3/baseline_final/**      (ÖNCE — gerçek production 9:16 karesi)
evidence/stage_5_3/solve_final/*.png      (SONRA — Blender-only kadraj kareleri)
evidence/stage_5_3/final/**/*.png         (SONRA — 3 format × kareler + contact_sheet.png)
```

Bu PNG'ler `collect_evidence.py` ve `probe_formats.py` ile her zaman yeniden üretilebilir;
yolları ve ölçümleri JSON'larda ve bu raporda sabittir. İstenirse kanıt görselleri ayrıca
commit edilebilir.

Frontend dosyalarında değişiklik **yok** (Bölüm 5.4). Kullanıcı verisi, veritabanı, sesler ve
mevcut render'lar silinmedi; hiçbir veri sıfırlanmadı; git geçmişi değiştirilmedi; push ve
deploy yapılmadı.

### Commit

```
e9f4c78  feat(studio): implement true vertical video composition
```

Kod, testler ve hafif kanıt artefaktları bu tek commit'te yer aldı; brief'in istediği commit
mesajı budur. Ardından yalnızca bu raporun SHA alanını doldurmak için küçük bir docs commit'i
daha yapıldı (`docs(studio): record Stage 5.3 commit SHA`) — bir commit'in kendi SHA'sını
içermesi mümkün olmadığından bu ayrılmaz bir sıralı düzeltmedir.

`.env`, `data/` ve `*.mp4` ignore altında; commit'a girmediler. Önceki aşamalara ait
`STAGE_5_1_*`, `STAGE_5_2_*` raporları ve `evidence/stage_5_2_1/` bu aşamanın kapsamı dışında
olduğu için stage edilmedi.

---

## 13. BİLİNEN SINIRLAMALAR

1. **Kapsama (letterbox) hâlâ fizik sınırına tabidir.** Yan yana iki karakter 9:16'da
   **genişlikten sınırlıdır** (`limited_by=width`): çerçevenin yüksekliğinin bir kısmı
   zorunlu olarak boş kalır. Çözüm karakterleri yaklaştırmak + kadrajı dize kadar açmak
   (doluluk 0.313 → 0.625); iki yanı da kesmeden daha fazlası geometrik olarak mümkün değil.
   Rig limitleri aşılırsa `fits=False` raporlanır ve WARNING düşer — sessiz kırpma yok.

2. **Metin katmanları kadraja göre yeniden akıtılmıyor.** `TextLayer` konumları
   (`anchor`, `y_ratio`) kullanıcı tarafından yazılıyor ve formattan bağımsız. 9:16 açılış
   karesinde başlık kutusu karakterlerin baş hizasına inebiliyor (yarı saydam arka plan
   yüzünden yüzler okunur kalıyor). Altyazılar güvenli alt bantla çakışmıyor; bu, kamera
   çözümlemesinin özne alt sınırını bilinçli olarak 0.80'in üstünde bırakması sayesinde.

3. **Backdrop kapsaması isim kalıbına bağlı.** `*Wall* / *Backdrop*` ve
   `Floor/Grass/Rug` adlı, rotasyonsuz ve ebeveynsiz nesneler büyütülüyor. Özel/harici
   setlerde (custom `.blend`) kalıp tutmazsa kadraj dışı siyah world background kalabilir;
   worker bu durumda `expand_backdrop_for_frame` boş liste döner ve hata vermez.

4. **Kamera çözümü level-axis yaklaşımı kullanıyor.** `TRACK_TO` ile küçük aşağı eğim
   (0.0–0.4 m) varsayılıyor; dikey konum izdüşümü lineer yaklaşık. Uç açı (dutch tilt,
   dik bakış) eklenirse rapor değerleri sapabilir — bugün böyle bir sahne üretilmiyor.

5. **`SceneCamera.fov` hâlâ kullanılmıyor.** Alan mevcut ama worker onu okumuyor; bu aşama
   kapsamı dışında bırakıldı (kapsamı büyütmemek için).

6. **Yerleştirilmemiş rig sahnede görünür kalıyor.** Bir sahne yalnızca Ali'yi
   place'ederse Ayşe önceki konumunda durmaya devam eder ve kadraj ölçümüne girer. Bu
   Stage 5.3'te değil, sahne-grafı semantiğinde bir kusurdur; kadraj davranışını güvenli
   tarafa çeker (görünen hiçbir şey kadraj dışına atılmaz) ama kök nedeni çözmez.

7. **Ses: ElevenLabs anahtarı yok.** Kanıt çıktılarının sesi macOS `say` / Yelda.
   Dikey kadrajla ilgisiz, ancak rapor dürüstlüğü için belirtiliyor.

8. **`framing` raporu kompozisyon manifestine taşınmıyor.** Kompozisyon motoru sahne
   render klasörlerini temizlediği için solve bilgisi yalnızca `render_result.json`
   (Blender-only probe) ve worker log'unda yaşıyor. Kompozisyon manifestine kopyalamak
   `RenderOutputMetadata` sözleşmesini genişletirdi; bu aşamada bilinçli olarak yapılmadı.

---

## 14. SONUÇ

**PASS**

Gerekçe:

- Üç formatın tamamı **gerçek Blender + FFmpeg render'ı** ile üretildi; FFprobe
  1920×1080 / 1080×1920 / 1080×1080, h264, yuv420p, 30 fps, AAC 44.1 kHz stereo, eşit
  17.067 s süre ve SRT varlığını doğruladı.
- 9:16'da siyah kenar bandı **0.000** ve özne kadraj yüksekliğinin **0.625**'ini, güvenli
  bandın **0.880**'ini dolduruyor — önceki durumda bu değerler 0.313 / 0.441 idi.
- Ali ve Ayşe'nin **iki yüzü de** üç zaman damgasında kesintisiz görünüyor; başlar güvenli
  üst bandın altında, gövdeler altyazı bandının üstünde. Altyazı karesinde hiçbir yüz
  örtülmüyor.
- 16:9 ve 1:1 kalitesi düşmedi; 16:9'daki başa-değme kusuru da düzeldi (güvenli alan ihlali
  kaldırıldı).
- 223 backend + 23 frontend test, production build, doctor ve E2E temiz; başarısızlık
  gizlenmedi veya skip edilmedi.
- Kamera artık teslim formatının fonksiyonu — brief'in "yalnızca 1080×1920 üretmek başarı
  değildir" ölçütü görsel ve sayısal kanıtla karşılandı.
