import React, { useEffect, useState } from 'react';
import { Info, Link2, Loader2, ShieldCheck } from 'lucide-react';
import { apiService } from '../services/api';
import { SocialAccount } from '../types/publish';
import { PlatformDescriptor } from '../types/creator';
import { YouTubeConnectionCard } from '../components/youtube/YouTubeConnectionCard';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';

export const ConnectedAccountsPage: React.FC = () => {
  const [account, setAccount] = useState<SocialAccount | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [platforms, setPlatforms] = useState<PlatformDescriptor[]>([]);

  const load = async () => {
    setIsLoading(true);
    try {
      const status = await apiService.getYouTubeStatus();
      setAccount(status.account);
      setIsConnected(status.connected);
    } catch {
      setIsConnected(false);
    } finally {
      setIsLoading(false);
    }
    apiService.listPlatforms().then(setPlatforms).catch(() => setPlatforms([]));
  };

  useEffect(() => {
    load();
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-xs text-slate-400">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Hesap durumu yükleniyor...
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6">
      <YouTubeConnectionCard account={account} isConnected={isConnected} onAccountChange={load} />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[#28C76F]" /> Token güvenliği
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
          <p>
            OAuth erişim ve yenileme tokenları macOS Keychain içinde saklanır. Token değerleri arayüze veya
            tarayıcıya aktarılmaz; backend yalnızca gerektiğinde yeniler.
          </p>
          <p className="text-slate-500 dark:text-[#7E7F96]">
            Mevcut bağlantı korunur. Yeniden yetkilendirme yalnızca analitik veya yorum izinleri gibi ek kapsamlar
            gerektiğinde ve sizin başlatmanızla yapılır; zorunlu OAuth akışı tetiklenmez.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Link2 className="h-4 w-4 text-[#7367F0]" /> Platformlar
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {platforms.length === 0 ? (
            <p className="text-xs text-slate-400">
              Platform bilgisi alınamadı. Bu sürüm yalnızca YouTube'u destekler.
            </p>
          ) : (
            platforms.map((platform) => (
              <div
                key={platform.id}
                className="flex flex-col gap-2 rounded-xl border border-slate-100 p-3 dark:border-white/[0.06] sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="text-xs font-bold text-slate-800 dark:text-white">{platform.display_name}</p>
                  <p className="text-[11px] text-slate-400">
                    {platform.implemented ? 'Bu sürümde aktif' : 'Bu sürümde desteklenmiyor'}
                  </p>
                </div>
                <span
                  className={`w-fit rounded-md px-2 py-0.5 text-[10px] font-bold ${
                    platform.implemented
                      ? 'bg-[#28C76F]/10 text-[#28C76F]'
                      : 'bg-slate-100 text-slate-500 dark:bg-white/[0.06]'
                  }`}
                >
                  {platform.implemented ? 'Bağlı' : 'Pasif'}
                </span>
              </div>
            ))
          )}
          <div className="flex items-start gap-2 rounded-xl bg-slate-50 p-3 text-[11px] text-slate-500 dark:bg-white/[0.03] dark:text-[#7E7F96]">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              Instagram, TikTok veya başka bir platform bu sürümde yoktur ve sahte entegrasyon gösterilmez.
              Yalnızca gerçekten desteklenen yetenekler listelenir.
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
