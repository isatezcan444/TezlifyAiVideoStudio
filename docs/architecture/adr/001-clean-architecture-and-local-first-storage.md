# ADR 001: Clean Architecture and Local-First Storage Foundation

## Durum
Kabul Edildi

## Bağlam
Tezlify AI Video Studio; gelecekte Blender 2.5D animasyon motoru, çoklu LLM sağlayıcıları ve sosyal medya yayınlama adaptörleri içerecek şekilde büyüyecektir. Bu karmaşıklığın yönetilebilmesi için iş kurallarının (Domain) harici araçlardan (Blender, FastAPI, SQLite, FFmpeg) tamamen bağımsız olması şarttır.

## Karar
1. **Clean Architecture Katmanları:**
   - **Domain:** Harici hiçbir kütüphane bağımlılığı içermeyen saf Python sınıfları (`MediaAsset`, `VideoMetadata`, `ImportRecord`, `MediaStatus`).
   - **Application:** Use case odaklı akışlar (`ImportVideoUseCase`, `GetMediaUseCase`, vb.), DTO'lar ve soyut Port/Arayüzler.
   - **Infrastructure:** Portların somut implementasyonları (`MediaRepositoryImpl`, `LocalMediaStorage`, `VideoProbeImpl`).
   - **Presentation:** FastAPI endpoint'leri, Pydantic v2 istek/cevap şemaları ve Dependency Injection kapsayıcısı.

2. **Yerel Depolama (Local-First):**
   - Videolar veritabanında değil, yerel dosya sisteminde (`data/media`) saklanır.
   - Veritabanı ve medya dizinleri `.gitignore` ile kaynak kod deposundan hariç tutulur.
   - Dosya yüklemeleri RAM şişmesini önlemek amacıyla parça parça (chunked stream) okunur ve anında SHA-256 hash'i çıkarılır.

3. **HTTP Range Desteği:**
   - HTML5 video oynatıcıların ileri ve geri sarma talepleri için HTTP 206 Partial Content akışı uygulanmıştır.

4. **Hata Yönetimi ve Dayanıklılık:**
   - FFprobe veya Blender sistemde yüklü olmasa dahi uygulama çökmez; pure-Python başlık okuma mekanizmasına geri çekilir.

