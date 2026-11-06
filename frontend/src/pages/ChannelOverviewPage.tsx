import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  BarChart3,
  ExternalLink,
  Eye,
  Film,
  Loader2,
  ListVideo,
  PlaySquare,
  RefreshCw,
  Users,
} from 'lucide-react';
import { apiService } from '../services/api';
import { useChannelContext } from '../context/ChannelContext';
import {
  AnalyticsDelta,
  AnalyticsResponse,
  ChannelOverviewResponse,
  ChannelVideo,
} from '../types/creator';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { StatsCard } from '../components/ui/StatsCard';
import { EmptyState } from '../components/ui/EmptyState';
import { formatDate, formatNumber } from '../lib/utils';
import { deltaClass, deltaLabel } from '../lib/analytics';

const errorMessage = (reason: unknown, fallback: string) => {
  if (reason && typeof reason === 'object' && 'message' in reason) {
    return String((reason as { message: unknown }).message);
  }
  return fallback;
};

export const ChannelOverviewPage: React.FC<{ onNavigate: (tab: string) => void }> = ({ onNavigate }) => {
  const { activeChannel } = useChannelContext();
  const channelId = activeChannel?.id;
  const [overview, setOverview] = useState<ChannelOverviewResponse | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [videosById, setVideosById] = useState<Record<string, ChannelVideo>>({});
  const [analyticsNotice, setAnalyticsNotice] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setIsLoading(true);
    setError(null);
    setAnalyticsNotice(null);
    const [overviewResult, analyticsResult, videosResult] = await Promise.allSettled([
      apiService.getChannelOverview(channelId),
      apiService.getChannelAnalytics({
        range: '28',
        dimensions: ['video'],
        compare: true,
        channelId,
      }),
      apiService.listChannelVideos(10, undefined, channelId),
    ]);

    if (overviewResult.status === 'fulfilled') {
      setOverview(overviewResult.value);
    } else {
      setError(errorMessage(overviewResult.reason, 'Kanal bilgisi alınamadı.'));
    }

    if (analyticsResult.status === 'fulfilled') {
      const response = analyticsResult.value;
      setAnalytics(response);
      if (!response.analytics.available) {
        setAnalyticsNotice(
          response.explanation || 'Analitik verisi şu anda kullanılamıyor.'
        );
      }
    } else {
      setAnalyticsNotice(
        errorMessage(analyticsResult.reason, 'Analitik verisi şu anda kullanılamıyor.')
      );
    }

    if (videosResult.status === 'fulfilled') {
      setVideosById(
        Object.fromEntries(
          videosResult.value.items.map((video) => [video.video_id, video])
        )
      );
    }

    setIsLoading(false);
  };

  useEffect(() => {
    setOverview(null);
    setAnalytics(null);
    setAnalyticsNotice(null);
    load();
  }, [channelId]);

  if (isLoading && !overview) {
    return (
      <div className="flex items-center justify-center py-24 text-xs text-slate-400">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Kanal bilgisi yükleniyor...
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Kanal verisi alınamadı"
        description={error}
        actionLabel="Bağlı Hesaplar"
        onAction={() => onNavigate('connected-accounts')}
      />
    );
  }

  if (!overview) return null;
  const channel = overview.channel;

  const analyticsData = analytics?.analytics;
  const analyticsReady = analyticsData?.available === true;
  const totals = analyticsData?.totals || {};
  const comparison = analytics?.comparison;
  const metricDelta = (metric: string) =>
    comparison?.available ? comparison.deltas?.[metric] : undefined;
  const netSubscribers =
    (totals.subscribersGained || 0) - (totals.subscribersLost || 0);
  const topVideos = analyticsReady ? (analyticsData?.rows || []).slice(0, 5) : [];

  const insights: Array<{
    key: string;
    label: string;
    value: string;
    delta?: AnalyticsDelta;
    caption?: string;
  }> = [
    {
      key: 'views',
      label: 'Görüntüleme',
      value: formatNumber(totals.views ?? 0),
      delta: metricDelta('views'),
    },
    {
      key: 'minutes',
      label: 'İzlenme süresi',
      value: `${formatNumber(totals.estimatedMinutesWatched ?? 0)} dk`,
      delta: metricDelta('estimatedMinutesWatched'),
    },
    {
      key: 'subscribers',
      label: 'Net abone',
      value: `${netSubscribers > 0 ? '+' : ''}${formatNumber(netSubscribers)}`,
      caption: `Kazanılan ${formatNumber(totals.subscribersGained ?? 0)} · Kaybedilen ${formatNumber(
        totals.subscribersLost ?? 0
      )}`,
    },
    {
      key: 'average',
      label: 'Ort. izlenme',
      value: `${formatNumber(totals.averageViewPercentage ?? 0)}%`,
      delta: metricDelta('averageViewPercentage'),
    },
  ];

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex flex-col gap-5 p-6 sm:flex-row sm:items-start">
          {channel.avatar_url ? (
            <img
              src={channel.avatar_url}
              alt={channel.title}
              className="h-20 w-20 rounded-2xl border border-slate-200 object-cover dark:border-white/10"
            />
          ) : (
            <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-[#7367F0]/10 text-[#7367F0]">
              <Users className="h-8 w-8" />
            </div>
          )}
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-extrabold text-slate-800 dark:text-white">{channel.title}</h2>
              <span className="rounded-md bg-[#28C76F]/10 px-2 py-0.5 text-[10px] font-bold text-[#28C76F]">
                YouTube Data API
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-[#7E7F96]">
              {channel.custom_url || channel.channel_id}
              {channel.country ? ` · ${channel.country}` : ''}
              {channel.published_at ? ` · Açılış: ${formatDate(channel.published_at)}` : ''}
            </p>
            {channel.description && (
              <p className="max-w-3xl whitespace-pre-line text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                {channel.description}
              </p>
            )}
            <div className="flex flex-wrap gap-2 pt-1">
              <a
                href={`https://www.youtube.com/channel/${channel.channel_id}`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-[11px] font-semibold text-slate-600 hover:border-[#7367F0]/40 hover:text-[#7367F0] dark:border-white/10 dark:text-slate-300"
              >
                Kanalı YouTube'da aç <ExternalLink className="h-3.5 w-3.5" />
              </a>
              <Button variant="ghost" size="sm" onClick={load} className="gap-1.5 text-xs">
                <RefreshCw className="h-3.5 w-3.5" /> Yenile
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatsCard
          title="Abone"
          value={channel.hidden_subscriber_count ? 'Gizli' : formatNumber(channel.subscriber_count)}
          icon={Users}
          variant="primary"
        />
        <StatsCard title="Toplam görüntüleme" value={formatNumber(channel.view_count)} icon={Eye} variant="info" />
        <StatsCard
          title="Video sayısı"
          value={formatNumber(channel.video_count)}
          subtitle="Yalnızca herkese açık videolar"
          icon={Film}
          variant="success"
        />
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Son 28 gün</CardTitle>
            <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
              YouTube Analytics API
              {analytics?.range
                ? ` · ${analytics.range.start_date} → ${analytics.range.end_date}`
                : ''}
              {comparison?.available && comparison.range
                ? ` · karşılaştırma ${comparison.range.start_date} → ${comparison.range.end_date}`
                : ''}
            </p>
          </div>
          <BarChart3 className="h-4 w-4 text-slate-400" />
        </CardHeader>
        <CardContent>
          {analyticsNotice ? (
            <div className="flex flex-col items-start gap-2 py-4">
              <p className="text-xs leading-relaxed text-slate-500 dark:text-[#7E7F96]">
                {analyticsNotice}
              </p>
              <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                Kanal bilgileri ve oynatma listeleri bu veriden bağımsız çalışmaya devam eder.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {insights.map((insight) => (
                <div
                  key={insight.key}
                  className="rounded-xl border border-slate-200 bg-white p-4 dark:border-white/[0.08] dark:bg-[#2F3349]"
                >
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-[#7E7F96]">
                    {insight.label}
                  </p>
                  <p className="mt-1 text-xl font-extrabold text-slate-800 dark:text-white">
                    {insight.value}
                  </p>
                  {insight.delta ? (
                    <p className={`mt-1 text-[10px] font-semibold ${deltaClass(insight.delta)}`}>
                      {deltaLabel(insight.delta)}
                    </p>
                  ) : insight.caption ? (
                    <p className="mt-1 text-[10px] text-slate-400 dark:text-[#7E7F96]">
                      {insight.caption}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {analyticsReady && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Öne çıkan videolar</CardTitle>
              <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                Son 28 gün · görüntülemeye göre ilk 5
              </p>
            </div>
            <PlaySquare className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            {topVideos.length === 0 ? (
              <p className="py-8 text-center text-xs text-slate-400">
                Bu dönemde video bazlı analitik veri yok.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-slate-200 text-[10px] font-bold uppercase text-slate-400 dark:border-white/[0.08]">
                    <tr>
                      <th className="py-2 pr-4">Video</th>
                      <th className="py-2 pr-4 text-right">Görüntüleme</th>
                      <th className="py-2 pr-4 text-right">İzlenme (dk)</th>
                      <th className="py-2 pr-4 text-right">Ort. süre (sn)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-white/[0.05]">
                    {topVideos.map((row) => {
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
                                <p className="truncate text-[10px] text-slate-400">{videoId}</p>
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
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Oynatma listeleri</CardTitle>
            <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">YouTube Data API · ilk 10 liste</p>
          </div>
          <ListVideo className="h-4 w-4 text-slate-400" />
        </CardHeader>
        <CardContent>
          {overview.playlists.length === 0 ? (
            <p className="py-8 text-center text-xs text-slate-400">Oynatma listesi bulunamadı.</p>
          ) : (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {overview.playlists.map((playlist) => (
                <div
                  key={playlist.playlist_id}
                  className="rounded-xl border border-slate-100 p-3 dark:border-white/[0.06]"
                >
                  <p className="truncate text-xs font-bold text-slate-800 dark:text-white">{playlist.title}</p>
                  <p className="text-[11px] text-slate-400">
                    {formatNumber(playlist.item_count)} video · {playlist.published_at ? formatDate(playlist.published_at) : '—'}
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={() => onNavigate('videos')}>Kanal videoları</Button>
        <Button size="sm" variant="outline" onClick={() => onNavigate('analytics')}>Analitik</Button>
        <Button size="sm" variant="outline" onClick={() => onNavigate('comments')}>Yorumlar</Button>
      </div>
    </div>
  );
};
