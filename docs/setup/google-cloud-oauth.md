# Google Cloud Console & YouTube OAuth 2.0 Kurulum Kılavuzu

Tezlify AI Video Studio'nun gerçek bir YouTube kanalına video yükleyebilmesi için bir Google Cloud projesi ve OAuth 2.0 Desktop istemcisi gereklidir.

## 1. Google Cloud Projesi Oluşturma
1. [Google Cloud Console](https://console.cloud.google.com/) adresine gidin.
2. Üst menüden **Select a Project** -> **New Project** seçeneğine tıklayın.
3. Proje Adı olarak `Tezlify Studio` yazın ve **Create** butonuna basın.

## 2. YouTube Data API v3 Etkinleştirme
1. Sol menüden **APIs & Services** -> **Library** bölümüne gidin.
2. Arama kutusuna `YouTube Data API v3` yazın.
3. Çıkan sonuca tıklayıp **Enable** butonuna basın.

## 3. OAuth İzin Ekranı (Consent Screen) Yapılandırma
1. **APIs & Services** -> **OAuth consent screen** sayfasına gidin.
2. User Type olarak **External** seçin ve **Create** butonuna basın.
3. Uygulama bilgilerini doldurun:
   - **App name**: `Tezlify AI Video Studio`
   - **User support email**: Kendi e-posta adresiniz
   - **Developer contact information**: Kendi e-posta adresiniz
4. **Scopes (Kapsamlar)** adımında **Add or Remove Scopes** butonuna tıklayın ve şu izinleri seçin:
   - `.../auth/youtube.upload` (Video yükleme)
   - `.../auth/youtube.readonly` (Kanal profili ve başlığını görüntüleme)
5. **Test users** adımında kendi Google hesabınızı test kullanıcısı olarak ekleyin (Uygulama Testing modundayken sadece eklenen kullanıcılar giriş yapabilir).
6. Kaydedip tamamlayın.

## 4. OAuth 2.0 Client ID Oluşturma
1. **APIs & Services** -> **Credentials** sayfasına gidin.
2. **Create Credentials** -> **OAuth client ID** seçeneğini seçin.
3. **Application type** olarak **Web application** seçin:
   - **Name**: `Tezlify Studio Local Client`
   - **Authorized redirect URIs**:
     - `http://127.0.0.1:8000/api/v1/social/youtube/callback`
     - `http://localhost:8000/api/v1/social/youtube/callback`
4. **Create** butonuna tıklayın.
5. Size verilen **Client ID** ve **Client Secret** değerlerini kopyalayın.

## 5. Tezlify AI Video Studio Yapılandırması (.env)
Proje kök dizinindeki `.env` dosyasını açın ve değerleri girin:

```env
# Google / YouTube OAuth Yapılandırması
GOOGLE_CLIENT_ID="XXXXXX-XXXXXXXX.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="GOCSPX-XXXXXXXXXXXXXX"
YOUTUBE_REDIRECT_URI="http://127.0.0.1:8000/api/v1/social/youtube/callback"
```

Uygulamayı başlattığınızda (`python scripts/start.py`), sol menüden **YouTube Publisher** sekmesine geçip **YouTube Kanalı Bağla** butonuna tıklayarak hesabınızı bağlayabilirsiniz.
