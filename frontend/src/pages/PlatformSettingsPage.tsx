import React, { useEffect, useState } from 'react';
import { CheckCircle2, Loader2, XCircle } from 'lucide-react';
import { apiService } from '../services/api';
import { PlatformDescriptor } from '../types/creator';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';

const CAPABILITY_LABELS: Record<string, string> = {
  connect_oauth: 'OAuth bağlantısı',
  upload_video: 'Video yükleme',
  read_channel: 'Kanal bilgisi',
  read_videos: 'Video listesi',
  update_video_metadata: 'Meta veri düzenleme',
  manage_playlists: 'Oynatma listeleri',
  analytics: 'Analitik',
  read_comments: 'Yorum okuma',
  write_comments: 'Yorum yazma',
  monetization_revenue: 'Gelir verisi',
};

export const PlatformSettingsPage: React.FC = () => {
  const [platforms, setPlatforms] = useState<PlatformDescriptor[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiService
      .listPlatforms()
      .then(setPlatforms)
      .catch((err) => setError(err.message || 'Platform bilgisi alınamadı.'))
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-xs text-slate-400">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Platformlar yükleniyor...
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Platform yetenekleri</CardTitle>
          <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
            Her yetenek gerçek adaptör durumunu yansıtır. Gelir verisi yalnızca parasal analitik izniyle çalışır.
          </p>
        </CardHeader>
        <CardContent className="space-y-5">
          {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
          {platforms.map((platform) => (
            <div key={platform.id} className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-slate-800 dark:text-white">{platform.display_name}</h4>
                <span className="rounded-md bg-[#28C76F]/10 px-2 py-0.5 text-[10px] font-bold text-[#28C76F]">
                  {platform.implemented ? 'Aktif' : 'Pasif'}
                </span>
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {Object.entries(platform.capabilities).map(([key, enabled]) => (
                  <div
                    key={key}
                    className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2 text-[11px] dark:border-white/[0.06]"
                  >
                    <span className="text-slate-600 dark:text-slate-300">{CAPABILITY_LABELS[key] || key}</span>
                    {enabled ? (
                      <span className="flex items-center gap-1 font-bold text-[#28C76F]">
                        <CheckCircle2 className="h-3.5 w-3.5" /> Açık
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 font-bold text-slate-400">
                        <XCircle className="h-3.5 w-3.5" /> Kapalı
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Kapsam notları</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
          <p>
            Yükleme ve kanal yönetimi mevcut OAuth izinleriyle çalışır. YouTube Analytics ve yorum işlemleri ek
            kapsamlar gerektirebilir; eksik kapsamdayken istekler açık hata mesajı döndürür, sahte değer üretilmez.
          </p>
          <p className="text-slate-500 dark:text-[#7E7F96]">
            Yeniden yetkilendirme gerektiğinde Bağlı Hesaplar sayfasından başlatabilirsiniz. Bu işlem ancak siz
            istediğinizde yapılır.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};
