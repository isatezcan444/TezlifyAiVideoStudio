import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  BarChart3,
  Download,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Wallet,
  Youtube,
} from 'lucide-react';
import { apiService } from '../services/api';
import { useChannelContext } from '../context/ChannelContext';
import { AnalyticsDelta, AnalyticsResponse, ChannelVideo } from '../types/creator';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { EmptyState } from '../components/ui/EmptyState';
import { formatCurrency, formatDateTime, formatNumber } from '../lib/utils';
import { deltaClass, deltaLabel } from '../lib/analytics';
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

const ANALYTICS_STATUS_LABELS: Record<string, string> = {
  active: 'aktif',
  scope_required: 'izin gerekli',
  reauth_required: 'yeniden bağlan',
  unavailable: 'kullanılamıyor',
  api_not_enabled: 'API kapalı',
  insufficient_scope: 'izin gerekli',
  not_connected: 'bağlantı yok',
  quota_exceeded: 'kota aşıldı',
  forbidden: 'erişim reddedildi',
  api_error: 'API hatası',
};

function csvCell(value: string | number | null | undefined): string {
  const text = value === null || value === undefined ? '' : String(value);
  return /[";\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function downloadCsv(filename: string, lines: (string | number)[][]) {
  const content =
    '\uFEFF' + lines.map((line) => line.map(csvCell).join(';')).join('\r\n');
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export const AnalyticsPage: React.FC<{ onNavigate: (tab: string) => void }> = ({ onNavigate }) => {
  const { activeChannel, connections, refresh } = useChannelContext();
  const channelId = activeChannel?.id;
  const connection = connections.find((item) => item.id === activeChannel?.platform_connection_id);
  const analyticsCapability = findCapability(connection, 'analytics');
  const revenueCapability = findCapability(connection, 'revenue');
  const [isGrantingAnalytics, setIsGrantingAnalytics] = useState(false);
  const [grantError, setGrantError] = useState<string | null>(null);
  const [isGrantingRevenue, setIsGrantingRevenue] = useState(false);
  const [revenueGrantError, setRevenueGrantError] = useState<string | null>(null);
  const [range, setRange] = useState('28');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [dimension, setDimension] = useState('day');
  const [includeRevenue, setIncludeRevenue] = useState(false);
  const [compare, setCompare] = useState(false);
  const [videosById, setVideosById] = useState<Record<string, ChannelVideo>>({});
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
          compare,
          channelId,
        })
      );
    } catch (err: any) {
      setError(err.message || 'Analitik verisi alınamadı.');
    } finally {
      setIsLoading(false);
    }
  }, [range, customStart, customEnd, dimension, includeRevenue, compare, channelId]);

  useEffect(() => {
    setData(null);
    load();
  }, [load]);

  useEffect(() => {
    if (
      (!includeRevenue && dimension !== 'video') ||
      (includeRevenue && revenueCapability?.status !== 'active') ||
      !channelId
    )
      return;
    let cancelled = false;
    apiService
      .listChannelVideos(50, undefined, channelId)
      .then((res) => {
        if (cancelled) return;
        setVideosById(
          Object.fromEntries(res.items.map((video) => [video.video_id, video]))
        );
      })
      .catch(() => {
        // Video başlıkları süsleme amaçlıdır; tablolar video kimliğiyle de çalışır.
      });
    return () => {
      cancelled = true;
    };
  }, [includeRevenue, dimension, revenueCapability?.status, channelId]);

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

  const handleGrantRevenue = async () => {
    if (!connection) return;
    setIsGrantingRevenue(true);
    setRevenueGrantError(null);
    try {
      const result = awaitYouTubeOAuth();
      const res = await apiService.grantCapabilities(connection.id, ['revenue']);
      openOAuthPopup(res.auth_url, `tezlify_grant_revenue_${connection.id}`);
      const success = await result;
      await refresh();
      if (success) await load();
      else
        setRevenueGrantError(
          'Gelir izni verilmedi. Mevcut hesap bağlantınız ve diğer izinler korunuyor.'
        );
    } catch (err: any) {
      setRevenueGrantError(err?.message || 'Gelir izni başlatılamadı.');
    } finally {
      setIsGrantingRevenue(false);
    }
  };

  const analytics = data?.analytics;
  const dimensionKey = dimension;
  const rows = analytics?.rows || [];
  const unavailableReason = analytics?.reason ?? null;

  const revenue = analytics?.revenue;
  const revenueCurrency = revenue?.currency || 'USD';
  const revenueDaily = revenue?.daily || [];
  const revenueVideos = revenue?.top_videos || [];
  const revenueMax = Math.max(
    0.01,
    ...revenueDaily.map((row) => row.metrics.estimatedRevenue || 0)
  );
  const revenueHasTrend = revenueDaily.some(
    (row) =>
      (row.metrics.estimatedRevenue || 0) > 0 || (row.metrics.estimatedAdRevenue || 0) > 0
  );
  const revenueDayCount = data?.range.days || revenueDaily.length || 1;
  const revenueAverage =
    revenue?.amount !== null && revenue?.amount !== undefined
      ? revenue.amount / revenueDayCount
      : null;

  const comparison = data?.comparison;

  const comparisonRowKey = (row: { dimensions: Record<string, string> }) =>
    (analytics?.dimensions?.length ? analytics.dimensions : [dimensionKey])
      .map((key) => row.dimensions[key] || '')
      .join('|');

  const comparisonRows = new Map(
    (comparison?.available ? comparison.rows || [] : []).map((row) => [row.key, row])
  );
  const hasRowComparison = comparisonRows.size > 0;

  const dimensionValue = (row: { dimensions: Record<string, string> }) => {
    const raw = row.dimensions[dimensionKey] || '';
    if (dimensionKey === 'video') return videosById[raw]?.title || raw || '—';
    return raw || '—';
  };

  const handleExportCsv = () => {
    if (!analytics || rows.length === 0) return;
    const dimensionLabel = DIMENSIONS.find((item) => item.key === dimensionKey)?.label || dimensionKey;
    const comparisonReady = compare && hasRowComparison;
    const metricHeader = (label: string) =>
      comparisonReady ? [label, `${label} (önceki)`, `${label} değişim %`] : [label];
    const metricCells = (
      metrics: Record<string, number>,
      rowComparison?: { previous_metrics: Record<string, number>; deltas: Record<string, AnalyticsDelta> }
    ) =>
      METRICS.flatMap((metric) => {
        const current = metrics[metric.key] ?? '';
        if (!comparisonReady) return [current];
        const previous = rowComparison?.previous_metrics?.[metric.key] ?? '';
        const delta = rowComparison?.deltas?.[metric.key];
        return [current, previous, delta?.percent ?? ''];
      });
    const lines: (string | number)[][] = [
      [dimensionLabel, ...METRICS.flatMap((metric) => metricHeader(metric.label))],
      ...rows.map((row) => [
        dimensionValue(row),
        ...metricCells(row.metrics, comparisonRows.get(comparisonRowKey(row))),
      ]),
      [
        'Toplam',
        ...metricCells(analytics.totals, comparison?.available
          ? { previous_metrics: comparison.totals || {}, deltas: comparison.deltas || {} }
          : undefined),
      ],
    ];
    downloadCsv(
      `tezlify-analitik-${dimensionKey}-${analytics.start_date}-${analytics.end_date}.csv`,
      lines
    );
  };

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
            <label className="flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-300">
              <input
                type="checkbox"
                checked={compare}
                onChange={(e) => setCompare(e.target.checked)}
                className="rounded border-slate-300"
              />
              Önceki dönemle karşılaştır
            </label>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportCsv}
              disabled={rows.length === 0}
              className="gap-1.5 text-xs"
              title="Görünen tabloyu CSV olarak indir"
            >
              <Download className="h-3.5 w-3.5" />
              CSV indir
            </Button>
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
                {ANALYTICS_STATUS_LABELS[
                  unavailableReason ?? analyticsCapability?.status ?? 'unavailable'
                ] ?? 'kullanılamıyor'}
              </span>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          {compare && comparison && (
            <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
              {comparison.available && comparison.range
                ? `Karşılaştırma dönemi: ${comparison.range.start_date} → ${comparison.range.end_date} (${comparison.range.days} gün)`
                : 'Önceki dönem verisi alınamadı; yalnızca seçili dönem gösteriliyor.'}
            </p>
          )}
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
            {METRICS.map((metric) => {
              const delta = comparison?.available
                ? comparison.deltas?.[metric.key]
                : undefined;
              return (
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
                  {delta && (
                    <p className={`mt-1 text-[10px] font-semibold ${deltaClass(delta)}`}>
                      {deltaLabel(delta)}
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>{DIMENSIONS.find((d) => d.key === dimensionKey)?.label} kırılımı</CardTitle>
                <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                  YouTube Analytics API · {analytics.start_date} → {analytics.end_date} ·{' '}
                  {formatDateTime(analytics.fetched_at)}
                </p>
                {hasRowComparison && comparison?.range && (
                  <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                    Her satırda {comparison.range.start_date} → {comparison.range.end_date} dönemine
                    göre değişim gösterilir.
                  </p>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {rows.length === 0 ? (
                <p className="py-10 text-center text-xs text-slate-400">Seçilen aralıkta veri yok.</p>
              ) : (
                <div className="overflow-x-auto" role="region" aria-label="Analitik kırılım tablosu" tabIndex={0}>
                  <p className="mb-2 text-[10px] text-slate-400 sm:hidden">Tüm metrikler için tabloyu yatay kaydırın.</p>
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-slate-200 text-[10px] font-bold uppercase text-slate-400 dark:border-white/[0.08]">
                      <tr>
                        <th className="whitespace-nowrap py-2 pr-4">{DIMENSIONS.find((d) => d.key === dimensionKey)?.label}</th>
                        {METRICS.map((metric) => (
                          <th key={metric.key} className="whitespace-nowrap py-2 pr-4 text-right">
                            {metric.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-white/[0.05]">
                      {rows.map((row, index) => {
                        const rowComparison = comparisonRows.get(comparisonRowKey(row));
                        const isNewRow = Boolean(
                          rowComparison &&
                            Object.keys(rowComparison.previous_metrics).length === 0
                        );
                        return (
                        <tr key={index}>
                          <td className="py-2 pr-4 font-semibold text-slate-700 dark:text-slate-200">
                            {dimensionKey === 'video' ? (
                              <a
                                href={`https://www.youtube.com/watch?v=${row.dimensions.video}`}
                                target="_blank"
                                rel="noreferrer"
                                className="hover:underline"
                              >
                                {dimensionValue(row)}
                              </a>
                            ) : (
                              dimensionValue(row)
                            )}
                          </td>
                          {METRICS.map((metric) => {
                            const delta = rowComparison?.deltas?.[metric.key];
                            return (
                              <td key={metric.key} className="py-2 pr-4 text-right">
                                <div className="text-slate-600 dark:text-slate-300">
                                  {formatNumber(row.metrics[metric.key])}
                                </div>
                                {delta ? (
                                  <div
                                    className={`text-[10px] font-semibold ${deltaClass(delta)}`}
                                    title={deltaLabel(delta)}
                                  >
                                    {delta.percent === null
                                      ? `${delta.change > 0 ? '+' : ''}${formatNumber(delta.change)}`
                                      : `${delta.percent > 0 ? '+' : ''}${delta.percent.toFixed(1)}%`}
                                  </div>
                                ) : isNewRow ? (
                                  <div className="text-[10px] font-semibold text-slate-400 dark:text-[#7E7F96]">
                                    yeni
                                  </div>
                                ) : null}
                              </td>
                            );
                          })}
                        </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {includeRevenue && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Gelir</CardTitle>
                  <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                    Tahmini reklam geliri · YouTube Analytics API · {revenueCurrency}
                  </p>
                </div>
                <span className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                  {CAPABILITY_META.revenue.label} ·{' '}
                  {ANALYTICS_STATUS_LABELS[revenueCapability?.status ?? 'unavailable'] ??
                    'kullanılamıyor'}
                </span>
              </CardHeader>
              <CardContent className="space-y-5">
                {revenueCapability?.status !== 'active' ? (
                  <>
                    <p className="text-xs leading-relaxed text-slate-500 dark:text-[#7E7F96]">
                      Gelir verisi için isteğe bağlı <code>yt-analytics-monetary.readonly</code>{' '}
                      izni gerekiyor. İzin yalnızca gelir raporunu açar; diğer özellikler bu izin
                      olmadan da çalışır.
                    </p>
                    {revenueGrantError && (
                      <p className="text-xs font-semibold text-amber-600 dark:text-amber-400">
                        {revenueGrantError}
                      </p>
                    )}
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        size="sm"
                        onClick={handleGrantRevenue}
                        disabled={isGrantingRevenue || !connection}
                        className="gap-2"
                      >
                        {isGrantingRevenue ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Youtube className="h-4 w-4" />
                        )}
                        {CAPABILITY_META.revenue.grantLabel}
                      </Button>
                    </div>
                  </>
                ) : revenue?.available ? (
                  <>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                      {[
                        { label: 'Toplam tahmini gelir', value: formatCurrency(revenue.amount, revenueCurrency) },
                        { label: 'Reklam geliri', value: formatCurrency(revenue.ad_revenue, revenueCurrency) },
                        { label: 'Günlük ortalama', value: formatCurrency(revenueAverage, revenueCurrency) },
                      ].map((item) => (
                        <div
                          key={item.label}
                          className="rounded-xl border border-slate-200 bg-white p-4 dark:border-white/[0.08] dark:bg-[#2F3349]"
                        >
                          <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-[#7E7F96]">
                            {item.label}
                          </p>
                          <p className="mt-1 flex items-center gap-1.5 text-xl font-extrabold text-slate-800 dark:text-white">
                            <Wallet className="h-4 w-4 text-emerald-500" />
                            {item.value}
                          </p>
                        </div>
                      ))}
                    </div>

                    {comparison?.available && comparison.revenue?.amount && (
                      <p
                        className={`text-[10px] font-semibold ${deltaClass(
                          comparison.revenue.amount
                        )}`}
                      >
                        Toplam gelir değişimi:{' '}
                        {formatCurrency(comparison.revenue.amount.change, revenueCurrency)} ·{' '}
                        {comparison.revenue.amount.percent === null
                          ? 'önceki dönemde gelir yok'
                          : `${comparison.revenue.amount.percent > 0 ? '+' : ''}${comparison.revenue.amount.percent.toFixed(1)}%`}{' '}
                        · önceki dönem{' '}
                        {formatCurrency(comparison.revenue.amount.previous, revenueCurrency)}
                      </p>
                    )}

                    <div>
                      <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-[#7E7F96]">
                        Günlük gelir · {data?.range.start_date} → {data?.range.end_date}
                      </p>
                      {revenueDaily.length === 0 || !revenueHasTrend ? (
                        <p className="py-8 text-center text-xs text-slate-400">
                          Bu dönemde raporlanmış gelir yok.
                        </p>
                      ) : (
                        <div className="flex h-40 items-end gap-1">
                          {revenueDaily.map((row) => (
                            <div
                              key={row.dimensions.day}
                              className="group relative flex-1 rounded-t bg-gradient-to-t from-emerald-500 to-emerald-300 transition hover:opacity-80"
                              style={{
                                height: `${Math.max(4, ((row.metrics.estimatedRevenue || 0) / revenueMax) * 100)}%`,
                              }}
                              title={`${row.dimensions.day}: ${formatCurrency(row.metrics.estimatedRevenue, revenueCurrency)}`}
                            />
                          ))}
                        </div>
                      )}
                    </div>

                    <div>
                      <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-[#7E7F96]">
                        Video bazlı gelir
                      </p>
                      {revenueVideos.length === 0 ? (
                        <p className="py-6 text-center text-xs text-slate-400">
                          Bu dönemde video bazlı gelir raporlanmadı.
                        </p>
                      ) : (
                        <div className="overflow-x-auto" role="region" aria-label="Video bazlı gelir tablosu" tabIndex={0}>
                          <p className="mb-2 text-[10px] text-slate-400 sm:hidden">Tüm sütunlar için tabloyu yatay kaydırın.</p>
                          <table className="w-full text-left text-xs">
                            <thead className="border-b border-slate-200 text-[10px] font-bold uppercase text-slate-400 dark:border-white/[0.08]">
                              <tr>
                                <th className="py-2 pr-4">Video</th>
                                <th className="py-2 pr-4 text-right">Görüntüleme</th>
                                <th className="py-2 pr-4 text-right">İzlenme (dk)</th>
                                <th className="py-2 pr-4 text-right">Ort. süre (sn)</th>
                                <th className="py-2 pr-4 text-right">Tahmini gelir</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-white/[0.05]">
                              {revenueVideos.map((row) => {
                                const videoId = row.dimensions.video;
                                const video = videosById[videoId];
                                return (
                                  <tr key={videoId}>
                                    <td className="py-2 pr-4">
                                      <div className="flex items-center gap-2.5">
                                        {video?.thumbnail_url ? (
                                          <img
                                            src={video.thumbnail_url}
                                            alt=""
                                            className="h-9 w-16 rounded object-cover"
                                          />
                                        ) : null}
                                        <div className="min-w-0">
                                          <a
                                            href={`https://www.youtube.com/watch?v=${videoId}`}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="block truncate font-semibold text-slate-700 hover:underline dark:text-slate-200"
                                          >
                                            {video?.title || videoId}
                                          </a>
                                          <p className="truncate text-[10px] text-slate-400">
                                            {videoId}
                                          </p>
                                        </div>
                                      </div>
                                    </td>
                                    <td className="py-2 pr-4 text-right text-slate-600 dark:text-slate-300">
                                      {formatNumber(row.metrics.views)}
                                    </td>
                                    <td className="py-2 pr-4 text-right text-slate-600 dark:text-slate-300">
                                      {formatNumber(row.metrics.estimatedMinutesWatched)}
                                    </td>
                                    <td className="py-2 pr-4 text-right text-slate-600 dark:text-slate-300">
                                      {formatNumber(row.metrics.averageViewDuration)}
                                    </td>
                                    <td className="py-2 pr-4 text-right font-semibold text-slate-700 dark:text-slate-200">
                                      {formatCurrency(row.metrics.estimatedRevenue, revenueCurrency)}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>

                    <p className="text-[11px] leading-relaxed text-slate-400 dark:text-[#7E7F96]">
                      {revenue.note}
                    </p>
                  </>
                ) : (
                  <p className="text-xs leading-relaxed text-slate-500 dark:text-[#7E7F96]">
                    {revenue?.note ||
                      'Gelir verisi döndürülmedi. Yalnızca yt-analytics-monetary.readonly izni olan kanallarda raporlanır; RPM/CPM ve reklam geliri birbirine karıştırılmaz.'}
                  </p>
                )}
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
