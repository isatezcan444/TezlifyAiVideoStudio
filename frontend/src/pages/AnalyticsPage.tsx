import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, BarChart3, Loader2, RefreshCw, ShieldAlert, Youtube } from 'lucide-react';
import { apiService } from '../services/api';
import { useChannelContext } from '../context/ChannelContext';
import { AnalyticsResponse } from '../types/creator';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { EmptyState } from '../components/ui/EmptyState';
import { formatDateTime, formatNumber } from '../lib/utils';
import { CAPABILITY_META, findCapability } from '../lib/capabilities';
import { awaitYouTubeOAuth, openOAuthPopup } from '../lib/youtubeOAuth';

const RANGES = [
  { key: '7', label: '7 gün' },
  { key: '28', label: '28 gün' },
  { key: '90', label: '90 gün' },
  { key: '365', label: '365 gün' },
];

const DIMENSIONS = [
  { key: 'day', label: 'Gün' },
  { key: 'trafficSourceType', label: 'Trafik kaynağı' },
  { key: 'country', label: 'Ülke' },
  { key: 'deviceType', label: 'Cihaz' },
  { key: 'video', label: 'Video' },
];

const METRICS = [
  { key: 'views', label: 'Görüntüleme' },
  { key: 'estimatedMinutesWatched', label: 'Tahmini izlenme (dk)' },
  { key: 'averageViewDuration', label: 'Ort. izlenme süresi (sn)' },
  { key: 'averageViewPercentage', label: 'Ort. izlenme %' },
  { key: 'subscribersGained', label: 'Kazanılan abone' },
  { key: 'subscribersLost', label: 'Kaybedilen abone' },
];

export const AnalyticsPage: React.FC<{ onNavigate: (tab: string) => void }> = ({ onNavigate }) => {
  const { activeChannel, connections, refresh } = useChannelContext();
  const channelId = activeChannel?.id;
  const connection = connections.find((item) => item.id === activeChannel?.platform_connection_id);
  const analyticsCapability = findCapability(connection, 'analytics');
  const [isGrantingAnalytics, setIsGrantingAnalytics] = useState(false);
  const [grantError, setGrantError] = useState<string | null>(null);
  const [range, setRange] = useState('28');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [dimension, setDimension] = useState('day');
  const [includeRevenue, setIncludeRevenue] = useState(false);
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const isCustom = range === 'custom';
      setData(
        await apiService.getChannelAnalytics({
          range: isCustom ? '28' : range,
          startDate: isCustom ? customStart : undefined,
          endDate: isCustom ? customEnd : undefined,
          dimensions: [dimension],
          includeRevenue,
          channelId,
        })
      );
    } catch (err: any) {
      setError(err.message || 'Analitik verisi alınamadı.');
    } finally {
      setIsLoading(false);
    }
  }, [range, customStart, customEnd, dimension, includeRevenue, channelId]);

  useEffect(() => {
    setData(null);
    load();
  }, [load]);

  const handleGrantAnalytics = async () => {
    if (!connection) return;
    setIsGrantingAnalytics(true);
    setGrantError(null);
    try {
      const result = awaitYouTubeOAuth();
      const res = await apiService.grantCapabilities(connection.id, ['analytics']);
      openOAuthPopup(res.auth_url, `tezlify_grant_analytics_${connection.id}`);
      const success = await result;
      await refresh();
      if (success) await load();
      else
        setGrantError(
          'Analytics izni verilmedi. Mevcut hesap bağlantınız ve diğer izinler korunuyor.'
        );
    } catch (err: any) {
      setGrantError(err?.message || 'Analytics izni başlatılamadı.');
    } finally {
      setIsGrantingAnalytics(false);
    }
  };

  const analytics = data?.analytics;
  const dimensionKey = dimension;
  const rows = analytics?.rows || [];
  const unavailableReason = analytics?.reason ?? null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 dark:border-white/[0.08] dark:bg-[#2F3349]">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-1">
            {RANGES.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setRange(item.key)}
                className={`rounded-lg px-3 py-1.5 text-[11px] font-bold transition ${
                  range === item.key
                    ? 'bg-[#7367F0] text-white shadow-sm'
                    : 'text-slate-500 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-white/[0.05]'
                }`}
              >
                {item.label}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setRange('custom')}
              className={`rounded-lg px-3 py-1.5 text-[11px] font-bold transition ${
                range === 'custom'
                  ? 'bg-[#7367F0] text-white shadow-sm'
                  : 'text-slate-500 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-white/[0.05]'
              }`}
            >
              Özel
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              value={dimension}
              onChange={(e) => setDimension(e.target.value)}
              className="vuexy-input rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs dark:border-white/10 dark:bg-white/[0.03]"
            >
              {DIMENSIONS.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.label}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-300">
              <input
                type="checkbox"
                checked={includeRevenue}
                onChange={(e) => setIncludeRevenue(e.target.checked)}
                className="rounded border-slate-300"
              />
              Gelir verisi iste
            </label>
            <Button variant="ghost" size="sm" onClick={load} disabled={isLoading} className="gap-1.5 text-xs">
              {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              Yenile
            </Button>
          </div>
        </div>

        {range === 'custom' && (
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500 dark:text-slate-300">
            <input
              type="date"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
              className="vuexy-input rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs dark:border-white/10 dark:bg-white/[0.03]"
            />
            <span>→</span>
            <input
              type="date"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
              className="vuexy-input rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs dark:border-white/10 dark:bg-white/[0.03]"
            />
            <span className="text-slate-400">En fazla 365 gün</span>
          </div>
        )}
      </div>

      {error ? (
        <EmptyState icon={AlertTriangle} title="Analitik yüklenemedi" description={error} />
      ) : isLoading && !data ? (
        <div className="flex items-center justify-center py-24 text-xs text-slate-400">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Analitik verisi yükleniyor...
        </div>
      ) : !analytics?.available ? (
        <Card>
          <CardContent className="space-y-3 p-8 text-center">
            <BarChart3 className="mx-auto h-8 w-8 text-slate-300" />
            <h3 className="text-sm font-bold text-slate-800 dark:text-white">
              {unavailableReason === 'api_not_enabled'
                ? 'YouTube Analytics API etkin değil'
                : unavailableReason === 'insufficient_scope'
                  ? 'Analytics izni gerekiyor'
                  : 'YouTube Analytics verisi kullanılamıyor'}
            </h3>
            <p className="mx-auto max-w-xl text-xs leading-relaxed text-slate-500 dark:text-[#7E7F96]">
              {unavailableReason === 'api_not_enabled'
                ? data?.explanation ||
                  'YouTube Analytics API bu Google Cloud projesinde etkin değil. API’yi Google Cloud Console üzerinden etkinleştirdikten sonra tekrar deneyin; yeni bir izin gerekmez.'
                : data?.explanation ||
                  'Analitik verisi alınamadı. Mevcut yükleme, kanal ve planlama özellikleri çalışmaya devam eder.'}
            </p>
            {grantError && (
              <p className="mx-auto max-w-xl text-xs font-semibold text-amber-600 dark:text-amber-400">
                {grantError}
              </p>
            )}
            <div className="flex flex-wrap items-center justify-center gap-2">
              {unavailableReason === 'insufficient_scope' ? (
                <Button
                  size="sm"
                  onClick={handleGrantAnalytics}
                  disabled={isGrantingAnalytics || !connection}
                  className="gap-2"
                >
                  {isGrantingAnalytics ? <Loader2 className="h-4 w-4 animate-spin" /> : <Youtube className="h-4 w-4" />}
                  {CAPABILITY_META.analytics.grantLabel}
                </Button>
              ) : unavailableReason === 'api_not_enabled' ? (
                <Button size="sm" variant="outline" onClick={() => onNavigate('connected-accounts')} className="gap-2">
                  <ShieldAlert className="h-4 w-4" /> Bağlı Hesaplar
                </Button>
              ) : (
                <Button size="sm" variant="outline" onClick={() => onNavigate('connected-accounts')}>
                  Bağlı Hesaplar
                </Button>
              )}
              <span className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                {CAPABILITY_META.analytics.label} ·{' '}
                {unavailableReason ?? analyticsCapability?.status ?? 'unavailable'}
              </span>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {METRICS.map((metric) => (
              <div
                key={metric.key}
                className="rounded-xl border border-slate-200 bg-white p-4 dark:border-white/[0.08] dark:bg-[#2F3349]"
              >
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-[#7E7F96]">
                  {metric.label}
                </p>
                <p className="mt-1 text-xl font-extrabold text-slate-800 dark:text-white">
                  {formatNumber(analytics.totals[metric.key])}
                </p>
              </div>
            ))}
          </div>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>{DIMENSIONS.find((d) => d.key === dimensionKey)?.label} kırılımı</CardTitle>
                <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                  YouTube Analytics API · {analytics.start_date} → {analytics.end_date} ·{' '}
                  {formatDateTime(analytics.fetched_at)}
                </p>
              </div>
            </CardHeader>
            <CardContent>
              {rows.length === 0 ? (
                <p className="py-10 text-center text-xs text-slate-400">Seçilen aralıkta veri yok.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-slate-200 text-[10px] font-bold uppercase text-slate-400 dark:border-white/[0.08]">
                      <tr>
                        <th className="py-2 pr-4">{DIMENSIONS.find((d) => d.key === dimensionKey)?.label}</th>
                        {METRICS.map((metric) => (
                          <th key={metric.key} className="py-2 pr-4 text-right">
                            {metric.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-white/[0.05]">
                      {rows.map((row, index) => (
                        <tr key={index}>
                          <td className="py-2 pr-4 font-semibold text-slate-700 dark:text-slate-200">
                            {row.dimensions[dimensionKey] || '—'}
                          </td>
                          {METRICS.map((metric) => (
                            <td key={metric.key} className="py-2 pr-4 text-right text-slate-600 dark:text-slate-300">
                              {formatNumber(row.metrics[metric.key])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {includeRevenue && (
            <Card>
              <CardHeader>
                <CardTitle>Gelir verisi</CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-slate-500 dark:text-[#7E7F96]">
                {analytics.revenue
                  ? JSON.stringify(analytics.revenue)
                  : 'Gelir verisi döndürülmedi. Yalnızca yt-analytics-monetary.readonly izni olan kanallarda raporlanır; RPM/CPM ve reklam geliri birbirine karıştırılmaz.'}
              </CardContent>
            </Card>
          )}

          <div className="space-y-1 rounded-xl bg-slate-50 p-4 text-[11px] leading-relaxed text-slate-500 dark:bg-white/[0.03] dark:text-[#7E7F96]">
            {Object.entries(data?.metric_notes || {}).map(([key, note]) => (
              <p key={key}>
                <strong className="text-slate-700 dark:text-slate-200">{key}:</strong> {note}
              </p>
            ))}
          </div>
        </>
      )}
    </div>
  );
};
