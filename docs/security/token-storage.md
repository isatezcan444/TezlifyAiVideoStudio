# Güvenlik & Token Saklama Mimarisi

Tezlify AI Video Studio, yerel odaklı (Local-First) bir masaüstü stüdyo mimarisine sahiptir. Kullanıcı güvenliği ve kimlik bilgisi koruması en yüksek önceliktir.

## 1. Sıfır Sızıntı (Zero-Exposure) Prensibi
- **Access Token ve Refresh Token Değerleri Frontend'e Asla Gönderilmez**: Tarayıcı tarafına yalnızca kanal adı, kanal ID'si ve maskeli avatar bilgisi iletilir.
- **Client Secret İzolasyonu**: Client Secret değeri sunucu tarafında `.env` içerisinde izole tutulur, hiçbir REST API yanıtında yer almaz.
- **CSRF Koruması**: OAuth oturumları RFC 7636 PKCE (Proof Key for Code Exchange) ve 10 dakikalık tek kullanımlık `state` parametresi ile güvenceye alınır.

## 2. macOS Keychain Entegrasyonu
Üretim ortamında OAuth tokenları SQLite veritabanında düz metin olarak DEĞİL, işletim sisteminin güvenli kasası olan macOS Keychain içinde saklanır:
- **CLI Entegrasyonu**: `/usr/bin/security` komut satırı aracı kullanılır.
- **Servis Adlandırma**: `TezlifyStudio_access` ve `TezlifyStudio_refresh`.
- **Erişim**: Yalnızca yerel backend sürecinin çalıştığı kullanıcı yetkileriyle erişilebilir.
- **Kanal Ayrımı**: Her bağlı kanal hesabı kendi benzersiz ID'si ile Keychain altında saklanır.
- **Bağlantı Kesildiğinde**: Kullanıcı "Bağlantıyı Kes" butonuna bastığında tokenlar Keychain'den kalıcı olarak `delete-generic-password` komutu ile imha edilir.

## 3. Test Ortamı Desteği
Otomatik testlerin (CI / headless koşumları) macOS Keychain izin pencerelerine takılmaması için `KeychainTokenStorageAdapter` otomatik test tespitli bellek içi adaptör (`InMemoryTokenStorageAdapter`) fallback mekanizmasına sahiptir.
