import React, { useState, useEffect } from 'react';
import { SocialAccount } from '../../types/publish';
import { apiService } from '../../services/api';
import { Button } from '../ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card';
import { Spinner } from '../ui/Spinner';

interface YouTubeConnectionCardProps {
  account: SocialAccount | null;
  isConnected: boolean;
  onAccountChange: () => void;
}

export const YouTubeConnectionCard: React.FC<YouTubeConnectionCardProps> = ({
  account,
  isConnected,
  onAccountChange,
}) => {
  const [isConnecting, setIsConnecting] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleAuthMessage = (event: MessageEvent) => {
      if (event.data?.type === 'TEZLIFY_YOUTUBE_CONNECTED') {
        setIsConnecting(false);
        onAccountChange();
      }
    };

    window.addEventListener('message', handleAuthMessage);
    return () => window.removeEventListener('message', handleAuthMessage);
  }, [onAccountChange]);

  const handleConnect = async () => {
    setError(null);
    setIsConnecting(true);
    try {
      const res = await apiService.connectYouTube();
      // Open Google OAuth in a popup window
      const width = 600;
      const height = 700;
      const left = window.screen.width / 2 - width / 2;
      const top = window.screen.height / 2 - height / 2;

      const popup = window.open(
        res.auth_url,
        'youtube_oauth_popup',
        `width=${width},height=${height},top=${top},left=${left},scrollbars=yes,status=1`
      );

      // Fallback timer to check if popup closed manually
      const checkClosed = setInterval(() => {
        if (!popup || popup.closed) {
          clearInterval(checkClosed);
          setIsConnecting(false);
          onAccountChange();
        }
      }, 1000);
    } catch (err: any) {
      setError(err.message || 'Google yetkilendirme linki alınamadı.');
      setIsConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm('YouTube kanal bağlantısını kaldırmak istediğinize emin misiniz?')) {
      return;
    }
    setIsDisconnecting(true);
    try {
      await apiService.disconnectYouTube();
      onAccountChange();
    } catch (err: any) {
      alert(`Bağlantı kesilemedi: ${err.message || 'Bilinmeyen hata'}`);
    } finally {
      setIsDisconnecting(false);
    }
  };

  return (
    <Card className="border border-[#7367F0]/20 bg-gradient-to-br from-white to-[#F8F7FA] dark:from-[#2F3349] dark:to-[#25293C]">
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center text-red-600 dark:text-red-400">
            <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor">
              <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
            </svg>
          </div>
          <div>
            <CardTitle className="text-base font-semibold text-[#4B465C] dark:text-[#DBD7EC]">
              YouTube Kanal Entegrasyonu
            </CardTitle>
            <p className="text-xs text-[#828092] dark:text-[#908DA1]">
              Resumable Video Yükleme ve Otomasyon Motoru (Google OAuth 2.0 PKCE)
            </p>
          </div>
        </div>

        {isConnected ? (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Bağlantı Aktif
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            <span className="w-2 h-2 rounded-full bg-amber-400"></span>
            Bağlı Değil
          </span>
        )}
      </CardHeader>

      <CardContent>
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-600 dark:text-red-400">
            {error}
          </div>
        )}

        {isConnected && account ? (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-slate-50 dark:bg-[#25293C] border border-slate-200/60 dark:border-slate-800">
            <div className="flex items-center gap-3.5">
              {account.channel_avatar_url ? (
                <img
                  src={account.channel_avatar_url}
                  alt={account.account_name}
                  className="w-12 h-12 rounded-full ring-2 ring-[#7367F0]/30 object-cover"
                />
              ) : (
                <div className="w-12 h-12 rounded-full bg-gradient-to-tr from-[#7367F0] to-[#9E95F5] text-white flex items-center justify-center font-bold text-lg">
                  {account.account_name.charAt(0).toUpperCase()}
                </div>
              )}
              <div>
                <h4 className="text-sm font-semibold text-[#4B465C] dark:text-[#DBD7EC]">
                  {account.account_name}
                </h4>
                <p className="text-xs text-[#828092] dark:text-[#908DA1] font-mono mt-0.5">
                  ID: {account.channel_id}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[11px] text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                    macOS Keychain Korumalı
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleDisconnect}
                disabled={isDisconnecting}
                className="text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-950/20 border-rose-200 dark:border-rose-900/40"
              >
                {isDisconnecting ? <Spinner size="sm" /> : 'Bağlantıyı Kes'}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-slate-50 dark:bg-[#25293C] border border-dashed border-slate-300 dark:border-slate-700">
            <div className="space-y-1">
              <p className="text-sm font-medium text-[#4B465C] dark:text-[#DBD7EC]">
                Henüz bir YouTube kanalı bağlanmamış
              </p>
              <p className="text-xs text-[#828092] dark:text-[#908DA1]">
                Doğrudan kanalınıza video yüklemek ve resumable yayın yönetimi için Google hesabınızı yetkilendirin.
              </p>
            </div>

            <Button
              onClick={handleConnect}
              disabled={isConnecting}
              className="bg-red-600 hover:bg-red-700 text-white shrink-0 gap-2 shadow-sm"
            >
              {isConnecting ? (
                <>
                  <Spinner size="sm" />
                  <span>Yetki Bekleniyor...</span>
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
                  </svg>
                  <span>YouTube Kanalı Bağla</span>
                </>
              )}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
