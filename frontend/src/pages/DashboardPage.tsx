import React, { useCallback, useEffect, useState } from 'react';
import {
  ArrowUpRight,
  ArrowDownRight,
  CalendarClock,
  Eye,
  Film,
  History,
  Loader2,
  RefreshCw,
  Users,
  Video as VideoIcon,
  AlertTriangle,
  ExternalLink,
} from 'lucide-react';
import { apiService } from '../services/api';
import { useChannelContext } from '../context/ChannelContext';
import { DashboardSnapshot } from '../types/creator';
import { StatsCard } from '../components/ui/StatsCard';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { EmptyState } from '../components/ui/EmptyState';
import { formatDateTime, formatNumber } from '../lib/utils';

const RANGES = [
  { key: '7', label: '7 gün' },
  { key: '28', label: '28 gün' },
  { key: '90', label: '90 gün' },
  { key: '365', label: '365 gün' },
];

const SOURCE_LABEL: Record<string, string> = {
  youtube_data_api: 'YouTube Data API',
  youtube_analytics_api: 'YouTube Analytics API',
  local_database: 'Yerel veritabanı',
};

const ANALYTICS_REASON_LABEL: Record<string, string> = {
  api_not_enabled: 'YouTube Analytics API kapalı',
  insufficient_scope: 'Analitik izni gerekli',
  quota_exceeded: 'Analitik kotası aşıldı',
};

const analyticsReasonLabel = (reason?: string | null): string =>
  (reason && ANALYTICS_REASON_LABEL[reason]) || 'Analitik kullanılamıyor';

const analyticsReasonDetail = (reason?: string | null): string => {
  if (reason === 'api_not_enabled') {
    return 'YouTube Analytics API bu Google Cloud projesinde etkin değil. Google Cloud Console üzerinden API\'yi etkinleştirmeniz gerekir.';
  }
  if (reason === 'insufficient_scope') {
    return 'Analitik verisi için gerekli yetki yok. Bağlı Hesaplar sayfasından YouTube bağlantısını yeniden yetkilendirebilirsiniz.';
  }
  if (reason === 'quota_exceeded') {
    return 'YouTube Analytics API kotası aşıldı. Kota sıfırlandığında veri yeniden yüklenecek.';
  }
  return 'Analitik verisi şu anda kullanılamıyor.';
};

const SourceBadge: React.FC<{ source?: string }> = ({ source }) => {
  if (!source) return null;
  return (
    <span className="inline-flex items-center rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-500 dark:bg-white/[0.06] dark:text-slate-300">
      {SOURCE_LABEL[source] || source}
    </span>
  );
};

export const DashboardPage: React.FC<{ onNavigate: (tab: string) => void }> = ({ onNavigate }) => {
  const { activeChannel } = useChannelContext();
  const [range, setRange] = useState('28');
  const [data, setData] = useState<DashboardSnapshot | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const channelId = activeChannel?.id;

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setData(await apiService.getDashboard(range, channelId));
    } catch (err: any) {
      setError(err.message || 'Panel verisi alınamadı.');
    } finally {
      setIsLoading(false);
    }
  }, [range, channelId]);

  useEffect(() => {
    setData(null);
    load();
  }, [load]);

  const analytics = data?.analytics;
  const dayRows = (analytics?.rows || []).filter((row) => row.dimensions.day);
  const maxViews = Math.max(1, ...dayRows.map((row) => row.metrics.views || 0));
  const gained = analytics?.totals.subscribersGained ?? null;
  const lost = analytics?.totals.subscribersLost ?? null;

  return (
    <div className="space-y-6">
      {/* Range + last updated */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white p-1 dark:border-white/[0.08] dark:bg-[#2F3349]">
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
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-400 dark:text-[#7E7F96]">
          {data?.last_updated && <span>Son güncelleme: {formatDateTime(data.last_updated)}</span>}
          <Button variant="ghost" size="sm" onClick={load} disabled={isLoading} className="gap-1.5 text-xs">
            {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Yenile
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {isLoading && !data ? (
        <div className="flex items-center justify-center py-24 text-xs text-slate-400">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Kanal durumu yükleniyor...
        </div>
      ) : !data?.connected ? (
        <EmptyState
          icon={Users}
          title="Bağlı YouTube kanalı yok"
          description="Gerçek abone, görüntüleme ve video verilerini görmek için YouTube kanalınızı bağlayın. Bağlantı macOS Keychain'de saklanır."
          actionLabel="Bağlı Hesaplar"
          onAction={() => onNavigate('connected-accounts')}
        />
      ) : (
        <>
          {/* Channel header */}
          <Card>
            <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-4">
                {data.channel?.avatar_url ? (
                  <img
                    src={data.channel.avatar_url}
                    alt={data.channel.title}
                    className="h-14 w-14 rounded-2xl border border-slate-200 object-cover dark:border-white/10"
                  />
                ) : (
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#7367F0]/10 text-[#7367F0]">
                    <VideoIcon className="h-6 w-6" />
                  </div>
                )}
                <div>
                  <h2 className="text-base font-extrabold text-slate-800 dark:text-white">
                    {data.channel?.title || 'YouTube Kanalı'}
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-[#7E7F96]">
                    {data.channel?.custom_url || data.channel?.channel_id || data.local_counts.account?.channel_id}
                  </p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <span className="inline-flex items-center gap-1 rounded-md bg-[#28C76F]/10 px-2 py-0.5 text-[10px] font-bold text-[#28C76F]">
                      Kanal bağlı
                    </span>
                    <SourceBadge source={data.sources.channel_status} />
                    <SourceBadge source={data.sources.subscribers} />
                  </div>
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={() => onNavigate('channel-overview')} className="gap-1.5">
                Kanal detayı <ExternalLink className="h-3.5 w-3.5" />
              </Button>
            </CardContent>
          </Card>

          {/* Warnings (e.g. missing analytics scope) */}
          {data.warnings.length > 0 && (
            <div className="space-y-2">
              {data.warnings.map((warning, index) => (
                <div
                  key={index}
                  className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300"
                >
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{warning}</span>
                </div>
              ))}
            </div>
          )}

          {/* Core stats (Data API) */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatsCard
              title="Abone"
              value={data.channel?.hidden_subscriber_count ? 'Gizli' : formatNumber(data.channel?.subscriber_count)}
              subtitle="YouTube Data API"
              icon={Users}
              variant="primary"
            />
            <StatsCard
              title="Toplam görüntüleme"
              value={formatNumber(data.channel?.view_count)}
              subtitle="YouTube Data API"
              icon={Eye}
              variant="info"
            />
            <StatsCard
              title="Video sayısı"
              value={formatNumber(data.channel?.video_count)}
              subtitle="YouTube Data API"
              icon={Film}
              variant="success"
            />
            <StatsCard
              title={`${range} gün görüntüleme`}
              value={analytics?.available ? formatNumber(analytics.totals.views) : 'Kullanılamıyor'}
              subtitle={analytics?.available ? 'YouTube Analytics API' : analyticsReasonLabel(analytics?.reason)}
              icon={ArrowUpRight}
              variant="warning"
            />
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            {/* Views over time */}
            <Card className="xl:col-span-2">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Görüntüleme eğilimi</CardTitle>
                  <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                    Günlük görüntüleme · <SourceBadge source={data.sources.views_over_time} />
                  </p>
                </div>
                <span className="text-[11px] text-slate-400">
                  {analytics?.start_date} → {analytics?.end_date}
                </span>
              </CardHeader>
              <CardContent>
                {!analytics?.available ? (
                  <p className="py-12 text-center text-xs text-slate-400">
                    {analyticsReasonDetail(analytics?.reason)}
                  </p>
                ) : dayRows.length === 0 ? (
                  <p className="py-12 text-center text-xs text-slate-400">Seçilen aralıkta günlük veri yok.</p>
                ) : (
                  <div className="flex h-48 items-end gap-1">
                    {dayRows.map((row) => (
                      <div
                        key={row.dimensions.day}
                        className="group relative flex-1 rounded-t bg-gradient-to-t from-[#7367F0] to-[#9E95F5] transition hover:opacity-80"
                        style={{ height: `${Math.max(4, ((row.metrics.views || 0) / maxViews) * 100)}%` }}
                        title={`${row.dimensions.day}: ${formatNumber(row.metrics.views)} görüntüleme`}
                      />
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Subscriber growth */}
            <Card>
              <CardHeader>
                <CardTitle>Abone değişimi</CardTitle>
                <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                  <SourceBadge source={data.sources.subscriber_growth} />
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between rounded-xl bg-[#28C76F]/10 p-4">
                  <span className="flex items-center gap-2 text-xs font-semibold text-[#28C76F]">
                    <ArrowUpRight className="h-4 w-4" /> Kazanılan
                  </span>
                  <span className="text-lg font-extrabold text-[#28C76F]">
                    {analytics?.available ? formatNumber(gained) : '—'}
                  </span>
                </div>
                <div className="flex items-center justify-between rounded-xl bg-[#EA5455]/10 p-4">
                  <span className="flex items-center gap-2 text-xs font-semibold text-[#EA5455]">
                    <ArrowDownRight className="h-4 w-4" /> Kaybedilen
                  </span>
                  <span className="text-lg font-extrabold text-[#EA5455]">
                    {analytics?.available ? formatNumber(lost) : '—'}
                  </span>
                </div>
                <div className="rounded-xl bg-slate-50 p-3 text-[11px] text-slate-500 dark:bg-white/[0.03] dark:text-[#7E7F96]">
                  Net değişim:{' '}
                  <strong className="text-slate-700 dark:text-white">
                    {analytics?.available && gained !== null && lost !== null
                      ? formatNumber((gained || 0) - (lost || 0))
                      : '—'}
                  </strong>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            {/* Recent uploads */}
            <Card className="xl:col-span-2">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Son yüklenen videolar</CardTitle>
                  <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                    <SourceBadge source={data.sources.recent_uploads} />
                  </p>
                </div>
                <Button variant="ghost" size="sm" className="text-xs" onClick={() => onNavigate('videos')}>
                  Tümünü gör
                </Button>
              </CardHeader>
              <CardContent className="space-y-2">
                {data.recent_videos.length === 0 ? (
                  <p className="py-8 text-center text-xs text-slate-400">Kanalda video bulunamadı.</p>
                ) : (
                  data.recent_videos.map((video) => (
                    <div
                      key={video.video_id}
                      className="flex items-center gap-3 rounded-xl border border-slate-100 p-2.5 dark:border-white/[0.06]"
                    >
                      {video.thumbnail_url ? (
                        <img src={video.thumbnail_url} alt="" className="h-12 w-20 rounded-lg object-cover" />
                      ) : (
                        <div className="flex h-12 w-20 items-center justify-center rounded-lg bg-slate-100 text-slate-400 dark:bg-white/[0.05]">
                          <Film className="h-4 w-4" />
                        </div>
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-bold text-slate-800 dark:text-white">{video.title}</p>
                        <p className="text-[11px] text-slate-400">
                          {formatNumber(video.view_count)} görüntüleme · {video.privacy_status || '—'}
                        </p>
                      </div>
                      <a
                        href={`https://www.youtube.com/watch?v=${video.video_id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-slate-400 hover:text-[#7367F0]"
                        aria-label="YouTube'da aç"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            {/* Upcoming schedules */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Yaklaşan yayınlar</CardTitle>
                  <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                    <SourceBadge source={data.sources.scheduled_uploads} />
                  </p>
                </div>
                <CalendarClock className="h-4 w-4 text-[#7367F0]" />
              </CardHeader>
              <CardContent className="space-y-2">
                {data.upcoming_schedules.length === 0 ? (
                  <p className="py-8 text-center text-xs text-slate-400">Planlanmış yayın yok.</p>
                ) : (
                  data.upcoming_schedules.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => onNavigate('scheduled-videos')}
                      className="w-full rounded-xl border border-slate-100 p-3 text-left transition hover:border-[#7367F0]/40 dark:border-white/[0.06]"
                    >
                      <p className="truncate text-xs font-bold text-slate-800 dark:text-white">{item.title}</p>
                      <p className="mt-0.5 text-[11px] text-slate-400">
                        {formatDateTime(item.scheduled_at_utc)} · {item.timezone}
                      </p>
                    </button>
                  ))
                )}
              </CardContent>
            </Card>
          </div>

          {/* Publish history */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Yayın geçmişi</CardTitle>
                <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                  <SourceBadge source={data.sources.publish_history} />
                </p>
              </div>
              <History className="h-4 w-4 text-slate-400" />
            </CardHeader>
            <CardContent>
              {data.recent_publishes.length === 0 ? (
                <p className="py-6 text-center text-xs text-slate-400">Henüz yayın kaydı yok.</p>
              ) : (
                <div className="space-y-2">
                  {data.recent_publishes.map((record) => (
                    <div
                      key={record.id}
                      className="flex flex-col gap-1 rounded-xl border border-slate-100 p-3 text-xs dark:border-white/[0.06] sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-bold text-slate-800 dark:text-white">{record.title}</p>
                        <p className="text-[11px] text-slate-400">
                          {formatDateTime(record.published_at || record.created_at)} · {record.privacy_status}
                        </p>
                      </div>
                      <span className="inline-flex w-fit rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600 dark:bg-white/[0.06] dark:text-slate-300">
                        {record.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <p className="text-[11px] leading-relaxed text-slate-400 dark:text-[#7E7F96]">
            Abone, görüntüleme ve video sayıları YouTube Data API'den; günlük analitik YouTube Analytics API'den;
            planlama ve yayın geçmişi yerel SQLite veritabanından gelir. Bir kaynak kullanılamadığında değer
            uydurulmaz, uyarı gösterilir.
          </p>
        </>
      )}
    </div>
  );
};
