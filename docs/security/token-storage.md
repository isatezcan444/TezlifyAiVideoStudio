# Güvenlik & Token Saklama Mimarisi

Tezlify AI Video Studio, yerel odaklı (Local-First) bir masaüstü stüdyo mimarisine sahiptir. Kullanıcı güvenliği ve kimlik bilgisi koruması en yüksek önceliktir.

---

## 1. Sıfır Sızıntı (Zero-Exposure) Prensibi
- **Access Token ve Refresh Token Değerleri Frontend'e Asla Gönderilmez**: Tarayıcı tarafına yalnızca kanal adı, kanal ID'si ve avatar bilgisi iletilir.
- **Upload Session URI Gizliliği**: Google'ın Resumable Upload oturum URI'si API yanıt modellerinden tamamen çıkarılmıştır.
- **Client Secret İzolasyonu**: İstemci kimlikleri backend ortamında `.env` içerisinde izole tutulur, hiçbir REST API yanıtında yer almaz.
- **RFC 7636 PKCE S256**: OAuth oturumları dinamik `code_verifier` ve `code_challenge` (SHA-256) ile korunur; yetkilendirme kodları üçüncü şahıslar tarafından kullanılamaz.
- **Tek Kullanımlık State**: 10 dakikalık TTL süresine sahip, doğrulanınca bellekten imha edilen CSRF korumalı oturum tokenları kullanılır.
- **Log İzolasyonu**: Dinamik loopback dinleyicisi ve API istemcisi, `code` veya gizli anahtarları loglara asla yazmaz.

---

## 2. macOS Keychain Entegrasyonu (Kesin Kalıcılık Garantisi)
Üretim ortamında OAuth tokenları SQLite veritabanında düz metin olarak DEĞİL, işletim sisteminin güvenli donanım destekli kasası olan macOS Keychain içinde saklanır:
- **CLI Entegrasyonu**: Doğrudan `/usr/bin/security` komut satırı aracı üzerinden `shell=False` ile güvenle çalıştırılır (kabuk enjeksiyon riski sıfırdır).
- **Servis Adlandırma**: `TezlifyStudio_access` ve `TezlifyStudio_refresh`.
- **Erişim & İzolasyon**: Yalnızca yerel işletim sistemi kullanıcısı yetkileriyle erişilebilir.
- **Güncelleme ve Silme**: `-U` bayrağı ile mevcut şifre atomik güncellenir; kanal bağlantısı kesildiğinde `delete-generic-password` komutu ile Keychain'den tamamen silinir.
- **Hata Yönetimi**: Keychain bulunamama durumu (`errSecItemNotFound`, dönüş kodu 44) boş token (`None`) olarak ele alınır; kilitli keychain veya yetki reddi durumlarında açık bir `TokenStorageException` fırlatılır.

---

## 3. Katı Üretim / Test Ayrımı
- **Üretimde Sessiz Fallback Yok**: `KeychainTokenStorageAdapter`, üretim ortamında asla sessizce hafıza belleğine düşmez (`fallback_to_memory=False`). Böylece uygulamanın yeniden başlatılması durumunda kullanıcının bağlı hesapları asla kaybolmaz.
- **Test ve CI Ortamı İzolasyonu**: `InMemoryTokenStorageAdapter`, sadece otomatik test koşucularında (`pytest` modülü veya `TEZLIFY_TEST_ENV=1`) dependency injection aracılığıyla devreye girer.
