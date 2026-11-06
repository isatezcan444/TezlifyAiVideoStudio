import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Loader2, XCircle } from 'lucide-react';
import { apiService } from '../services/api';
import { CapabilityStatus, PlatformConnection } from '../types/account';
import { PlatformDescriptor } from '../types/creator';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';

const CAPABILITY_LABELS: Record<string, string> = {
  connect_oauth: 'Hesap bağlama',
  disconnect: 'Bağlantıyı kesme',
  list_accounts: 'Hesap listesi',
  list_channels: 'Kanal listesi',
  get_channel_profile: 'Kanal profili',
  list_videos: 'Video listesi',
  upload_video: 'Video yükleme',
  update_video: 'Video güncelleme',
  get_analytics: 'Analytics',
  read_comments: 'Yorum okuma',
  write_comments: 'Yorum yazma',
  schedule_publish: 'Planlı yayın',
  monetization_revenue: 'Gelir verisi',
};

const UNKNOWN_CAPABILITY_LABEL = 'Tanımsız yetenek';

const ANALYTICS_STATES: Record<
  string,
  { label: string; className: string; icon: 'ok' | 'off' | 'warn' }
> = {
  active: {
    label: 'Açık',
    className: 'text-[#28C76F]',
    icon: 'ok',
  },
  scope_required: {
    label: 'İzin gerekli',
    className: 'text-amber-600 dark:text-amber-400',
    icon: 'warn',
  },
  api_not_enabled: {
    label: 'API kapalı',
    className: 'text-orange-600 dark:text-orange-400',
    icon: 'off',
  },
  reauth_required: {
    label: 'Yeniden bağlan',
    className: 'text-rose-600 dark:text-rose-400',
    icon: 'warn',
  },
  unavailable: {
    label: 'Kullanılamıyor',
    className: 'text-slate-400',
    icon: 'off',
  },
};

function resolveAnalyticsStatus(
  connections: PlatformConnection[]
): CapabilityStatus | undefined {
  const statuses = connections.flatMap(
    (connection) =>
      connection.capabilities?.filter((item) => item.capability === 'analytics') ?? []
  );
  return (
    statuses.find((item) => item.status === 'api_not_enabled') ??
    statuses.find((item) => item.status === 'reauth_required') ??
    statuses.find((item) => item.status === 'scope_required') ??
    statuses.find((item) => item.status === 'active') ??
    statuses[0]
  );
}

export const PlatformSettingsPage: React.FC = () => {
  const [platforms, setPlatforms] = useState<PlatformDescriptor[]>([]);
  const [connections, setConnections] = useState<PlatformConnection[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiService.listPlatforms(),
      apiService.listConnections(false).catch(() => ({ items: [], total: 0 })),
    ])
      .then(([platformList, connectionsRes]) => {
        setPlatforms(platformList);
        setConnections(connectionsRes.items);
      })
      .catch((err) => setError(err.message || 'Platform bilgisi alınamadı.'))
      .finally(() => setIsLoading(false));
  }, []);

  const analyticsStatus = resolveAnalyticsStatus(connections);

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
                {Object.entries(platform.capabilities).map(([key, enabled]) => {
                  const isAnalytics = key === 'get_analytics';
                  const statusMeta =
                    isAnalytics && enabled && analyticsStatus
                      ? ANALYTICS_STATES[analyticsStatus.status]
                      : undefined;
                  const StatusIcon =
                    statusMeta?.icon === 'ok'
                      ? CheckCircle2
                      : statusMeta?.icon === 'warn'
                        ? AlertTriangle
                        : XCircle;
                  return (
                    <div
                      key={key}
                      className="flex items-center justify-between gap-2 rounded-lg border border-slate-100 px-3 py-2 text-[11px] dark:border-white/[0.06]"
                    >
                      <div className="min-w-0">
                        <span className="text-slate-600 dark:text-slate-300">
                          {CAPABILITY_LABELS[key] ?? UNKNOWN_CAPABILITY_LABEL}
                        </span>
                        {isAnalytics && enabled && (
                          <span className="ml-1 text-[9px] font-normal text-slate-400">
                            adaptör desteği var
                          </span>
                        )}
                      </div>
                      {isAnalytics ? (
                        statusMeta ? (
                          <span
                            className={`flex shrink-0 items-center gap-1 font-bold ${statusMeta.className}`}
                          >
                            <StatusIcon className="h-3.5 w-3.5" /> {statusMeta.label}
                          </span>
                        ) : enabled ? (
                          <span className="flex shrink-0 items-center gap-1 font-bold text-slate-500">
                            <CheckCircle2 className="h-3.5 w-3.5" /> Adaptör destekliyor
                          </span>
                        ) : (
                          <span className="flex shrink-0 items-center gap-1 font-bold text-slate-400">
                            <XCircle className="h-3.5 w-3.5" /> Kapalı
                          </span>
                        )
                      ) : enabled ? (
                        <span className="flex shrink-0 items-center gap-1 font-bold text-[#28C76F]">
                          <CheckCircle2 className="h-3.5 w-3.5" /> Açık
                        </span>
                      ) : (
                        <span className="flex shrink-0 items-center gap-1 font-bold text-slate-400">
                          <XCircle className="h-3.5 w-3.5" /> Kapalı
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          {analyticsStatus?.status === 'api_not_enabled' && (
            <div className="flex items-start gap-2 rounded-lg border border-orange-200 bg-orange-50 p-3 text-[11px] leading-relaxed text-orange-700 dark:border-orange-500/20 dark:bg-orange-500/10 dark:text-orange-300">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                <strong>YouTube Analytics API etkin değil.</strong> Adaptör bu yeteneği destekliyor; bağlı
                hesabın Google Cloud projesinde YouTube Analytics API etkin olmadığı için veri alınamıyor.
                Google Cloud Console üzerinden API'yi etkinleştirmeniz gerekir. İzin vermek bu sorunu çözmez;
                sahte veri gösterilmez.
              </span>
            </div>
          )}
          {analyticsStatus?.status === 'scope_required' && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-[11px] leading-relaxed text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                Adaptör Analytics'i destekliyor; bağlı hesapta Analytics izni eksik. İzni Bağlı Hesaplar
                sayfasından verebilirsiniz.
              </span>
            </div>
          )}
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
