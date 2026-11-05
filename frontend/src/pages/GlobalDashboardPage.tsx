import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CalendarClock, Layers, Loader2, RefreshCw, UploadCloud, Users } from 'lucide-react';
import { apiService } from '../services/api';
import { GlobalDashboard } from '../types/account';
import { StatsCard } from '../components/ui/StatsCard';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { EmptyState } from '../components/ui/EmptyState';
import { formatDateTime } from '../lib/utils';

export const GlobalDashboardPage: React.FC<{ onNavigate: (tab: string) => void }> = ({ onNavigate }) => {
  const [data, setData] = useState<GlobalDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setData(await apiService.getGlobalDashboard());
    } catch (err: any) {
      setError(err?.message || 'Genel panel verisi alınamadı.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (isLoading && !data) {
    return (
      <div className="flex items-center justify-center py-24 text-xs text-slate-400">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Genel panel yükleniyor...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <span>{error}</span>
      </div>
    );
  }

  if (!data?.connected) {
    return (
      <EmptyState
        icon={Users}
        title="Bağlı hesap yok"
        description="Genel panel, bağlı platform hesaplarını ve yerel yayın kayıtlarını özetler. Başlamak için bir YouTube hesabı bağlayın."
        actionLabel="Bağlı Hesaplar"
        onAction={() => onNavigate('connected-accounts')}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-bold text-slate-800 dark:text-white">Çalışma Alanı Genel Bakışı</h2>
          <p className="text-xs text-slate-500 dark:text-[#7E7F96]">
            Hesap, kanal ve yerel yayın kayıtları. YouTube metrikleri kanal bazında ayrı gösterilir.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={load} disabled={isLoading} className="gap-1.5 text-xs">
          {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          Yenile
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatsCard title="Bağlı hesap" value={String(data.totals.accounts)} subtitle="Yerel veritabanı" icon={Users} variant="primary" />
        <StatsCard title="Yönetilen kanal" value={String(data.totals.channels)} subtitle="Yerel veritabanı" icon={Layers} variant="info" />
        <StatsCard title="Yayın kaydı" value={String(data.totals.publish_records)} subtitle="Yerel veritabanı" icon={UploadCloud} variant="success" />
        <StatsCard title="Planlanan yayın" value={String(data.totals.scheduled_records)} subtitle="Yerel veritabanı" icon={CalendarClock} variant="warning" />
      </div>

      {data.unresolved_publish_records > 0 && (
        <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            {data.unresolved_publish_records} eski yayın kaydının hangi kanala ait olduğu kesin değil.
            Bu kayıtlar tahmin edilmedi; <strong>unresolved</strong> olarak korunuyor.
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Platform özeti</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.platforms.map((platform) => (
              <div
                key={platform.platform}
                className="flex items-center justify-between rounded-xl border border-slate-100 p-3 dark:border-white/[0.06]"
              >
                <div>
                  <p className="text-xs font-bold text-slate-800 dark:text-white">{platform.display_name}</p>
                  <p className="text-[11px] text-slate-400">
                    {platform.accounts} hesap · {platform.channels} kanal
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs font-bold text-slate-700 dark:text-slate-200">
                    {platform.publish_records} yayın
                  </p>
                  <p className="text-[11px] text-slate-400">{platform.scheduled_records} plan</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Bağlı hesaplar</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.accounts.map((account) => (
              <div
                key={account.id}
                className="rounded-xl border border-slate-100 p-3 dark:border-white/[0.06]"
              >
                <div className="flex items-center justify-between">
                  <p className="text-xs font-bold text-slate-800 dark:text-white">
                    {account.account_display_name}
                  </p>
                  <span
                    className={`rounded-md px-2 py-0.5 text-[10px] font-bold ${
                      account.connection_status === 'active'
                        ? 'bg-emerald-500/10 text-emerald-600'
                        : 'bg-slate-100 text-slate-500 dark:bg-white/[0.06]'
                    }`}
                  >
                    {account.connection_status}
                  </span>
                </div>
                <p className="mt-1 text-[11px] text-slate-400">
                  {account.channel_count} kanal · {account.platform}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {account.channels.map((channel) => (
                    <span
                      key={channel.id}
                      className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600 dark:bg-white/[0.06] dark:text-slate-300"
                    >
                      {channel.channel_name}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Kaynaklar ve notlar</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-[11px] text-slate-500 dark:text-[#7E7F96]">
          {data.notes.map((note, index) => (
            <p key={index}>• {note}</p>
          ))}
          <p className="text-[10px] text-slate-400">
            Son yerel güncelleme: {formatDateTime(new Date().toISOString())}
          </p>
        </CardContent>
      </Card>
    </div>
  );
};
