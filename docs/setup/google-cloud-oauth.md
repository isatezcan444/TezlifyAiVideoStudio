# Google Cloud Console & YouTube OAuth 2.0 (Desktop App) Kurulum Kılavuzu

Tezlify AI Video Studio, macOS üzerinde yerel (local-first) çalışan bir masaüstü stüdyo uygulamasıdır. Google'ın resmî **Desktop / Native Application (RFC 8252)** OAuth 2.0 standartlarına tam uyumlu olarak çalışır.

---

## 1. Google Cloud Projesi Oluşturma

1. [Google Cloud Console](https://console.cloud.google.com/) adresine gidin.
2. Üst menüden **Select a Project** -> **New Project** seçeneğine tıklayın.
3. Proje Adı olarak `Tezlify Video Studio` yazın ve **Create** butonuna basın.

---

## 2. YouTube Data API v3 Etkinleştirme

1. Sol menüden **APIs & Services** -> **Library** (Kütüphane) bölümüne gidin.
2. Arama kutusuna `YouTube Data API v3` yazın.
3. Çıkan sonuca tıklayıp **Enable** (Etkinleştir) butonuna basın.

---

## 3. OAuth İzin Ekranı (OAuth Consent Screen) Yapılandırma

1. **APIs & Services** -> **OAuth consent screen** sayfasına gidin.
2. User Type olarak **External** seçin ve **Create** butonuna basın.
3. Uygulama bilgilerini doldurun:
   - **App name**: `Tezlify AI Video Studio`
   - **User support email**: Kendi Google e-posta adresiniz.
   - **Developer contact information**: Kendi Google e-posta adresiniz.
4. **Scopes (Kapsamlar)** adımında **Add or Remove Scopes** butonuna tıklayın ve şu iki izni seçin:
   - `.../auth/youtube.upload` (Videoları YouTube kanalına yükleme)
   - `.../auth/youtube.readonly` (Kanal profili, başlığı ve avatarını görüntüleme)
5. **Test users (Test Kullanıcıları)** adımında:
   - **ÖNEMLİ:** Uygulamanız "Testing" (Geliştirme/Test) modundayken Google doğrulaması gerekmez. Ancak video yükleyeceğiniz kendi YouTube hesabınızı **+ ADD USERS** butonuna tıklayarak buraya eklemeniz zorunludur. (Google, test aşamasında 100 kullanıcıya kadar izin verir).
6. Kaydedip tamamlayın.

---

## 4. OAuth 2.0 İstemcisi Oluşturma (ÖNEMLİ: Masaüstü Uygulaması)

> [!IMPORTANT]
> İstemci türü olarak kesinlikle **Web Application** değil, **Desktop App (Masaüstü Uygulaması)** seçilmelidir.
> Web istemcileri sabit port zorunluluğu getirirken, Desktop istemcileri Google tarafından RFC 8252 loopback IP (`127.0.0.1:{dynamic_port}`) yönlendirmelerine otomatik izin verir.

1. **APIs & Services** -> **Credentials** sayfasına gidin.
2. **Create Credentials** -> **OAuth client ID** seçeneğini seçin.
3. **Application type** açılır menüsünden **Desktop app** (Masaüstü uygulaması) seçeneğini seçin:
   - **Name**: `Tezlify Studio Desktop Client`
4. **Create** butonuna tıklayın. (Redirect URI girmeniz istenmeyecektir; Google Desktop istemcileri tüm `127.0.0.1` portlarını otomatik kabul eder).
5. Ekrana gelen **Client ID** ve **Client Secret** değerlerini kopyalayın (veya `client_secret_*.json` dosyasını indirin).

---

## 5. Güvenlik Notu: Masaüstü İstemcilerinde Client Secret & PKCE

- Masaüstü uygulamaları (Desktop Clients) OAuth 2.0 şartnamesinde **Public Client** kabul edilir; kullanıcı bilgisayarına dağıtılan hiçbir sır tamamen gizlenemez.
- Tezlify AI Video Studio, yetkilendirme güvenliğini **RFC 7636 PKCE (Proof Key for Code Exchange) S256** ile garanti eder.
- Her yetkilendirme isteğinde anlık, yüksek entropili bir `code_verifier` ve SHA-256 tabanlı `code_challenge` üretilir.
- Çalınan veya yetkisiz erişilen yetkilendirme kodları, yalnızca stüdyonun hafızasındaki gizli verifier ile geçerli olabileceğinden üçüncü şahıslar tarafından kullanılamaz.

---

## 6. Tezlify AI Video Studio Yapılandırması (.env)

Proje kök dizinindeki `.env` dosyasını açın ve edindiğiniz istemci anahtarlarını girin:

```env
# Google / YouTube OAuth Yapılandırması (Desktop App)
GOOGLE_CLIENT_ID="XXXXXX-XXXXXXXX.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="GOCSPX-XXXXXXXXXXXXXX"
```

---

## 7. İlk Bağlantı ve Test

1. Stüdyoyu başlatın:
   ```bash
   python scripts/start.py
   ```
2. Tarayıcıda `http://localhost:5173` adresine gidin.
3. Sol menüden **YouTube Publisher** sekmesini seçin.
4. **YouTube Kanalı Bağla** butonuna tıklayın:
   - Stüdyo anlık dinamik bir portta (örn. `http://127.0.0.1:54321/oauth2callback`) geçici bir döngü dinleyicisi başlatır.
   - Tarayıcınızda resmî Google hesap seçim ekranı açılır.
   - Onay verdiğinizde Google tarayıcıyı yerel dinleyiciye yönlendirir.
   - Kod PKCE ile doğrulanarak `access_token` ve `refresh_token` alınır.
   - Tokenlar sisteminizin **macOS Keychain** kasasına kaydedilir ve geçici yerel port derhal kapatılır.
