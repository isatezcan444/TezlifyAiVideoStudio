import React, { useEffect, useState } from 'react';
import { ExternalLink, Loader2, RefreshCw, Users, Eye, Film, ListVideo, AlertTriangle } from 'lucide-react';
import { apiService } from '../services/api';
import { useChannelContext } from '../context/ChannelContext';
import { ChannelOverviewResponse } from '../types/creator';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { StatsCard } from '../components/ui/StatsCard';
import { EmptyState } from '../components/ui/EmptyState';
import { formatDate, formatNumber } from '../lib/utils';

export const ChannelOverviewPage: React.FC<{ onNavigate: (tab: string) => void }> = ({ onNavigate }) => {
  const { activeChannel } = useChannelContext();
  const channelId = activeChannel?.id;
  const [data, setData] = useState<ChannelOverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setIsLoading(true);
    setError(null);
    try {
      setData(await apiService.getChannelOverview(channelId));
    } catch (err: any) {
      setError(err.message || 'Kanal bilgisi alınamadı.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    setData(null);
    load();
  }, [channelId]);

  if (isLoading && !data) {
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

  if (!data) return null;
  const channel = data.channel;

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
        <StatsCard title="Video sayısı" value={formatNumber(channel.video_count)} icon={Film} variant="success" />
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Oynatma listeleri</CardTitle>
            <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">YouTube Data API · ilk 10 liste</p>
          </div>
          <ListVideo className="h-4 w-4 text-slate-400" />
        </CardHeader>
        <CardContent>
          {data.playlists.length === 0 ? (
            <p className="py-8 text-center text-xs text-slate-400">Oynatma listesi bulunamadı.</p>
          ) : (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {data.playlists.map((playlist) => (
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
