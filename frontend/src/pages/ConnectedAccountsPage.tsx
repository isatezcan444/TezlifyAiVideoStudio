import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Info,
  Loader2,
  Plus,
  RefreshCw,
  ShieldCheck,
  Unplug,
  Youtube,
} from 'lucide-react';
import { apiService } from '../services/api';
import { useChannelContext } from '../context/ChannelContext';
import { CapabilityStatus, PlatformConnection } from '../types/account';
import { PlatformDescriptor } from '../types/creator';
import { CAPABILITY_META, CapabilityName } from '../lib/capabilities';
import { awaitYouTubeOAuth, openOAuthPopup } from '../lib/youtubeOAuth';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';

const PLATFORM_META: Record<string, { label: string; color: string }> = {
  youtube: { label: 'YouTube', color: 'text-red-600 bg-red-500/10' },
  instagram: { label: 'Instagram', color: 'text-pink-600 bg-pink-500/10' },
  tiktok: { label: 'TikTok', color: 'text-slate-800 bg-slate-900/10 dark:text-white dark:bg-white/10' },
};

const formatDate = (value?: string | null): string => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('tr-TR');
};

const CAPABILITY_ORDER: CapabilityName[] = [
  'channel_read',
  'analytics',
  'upload',
  'comments',
  'revenue',
];

const CAPABILITY_STATE: Record<string, { label: string; className: string }> = {
  active: { label: 'aktif', className: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' },
  scope_required: { label: 'izin gerekli', className: 'bg-amber-500/10 text-amber-600 dark:text-amber-400' },
  api_not_enabled: { label: 'API kapalı', className: 'bg-orange-500/10 text-orange-600 dark:text-orange-400' },
  reauth_required: { label: 'yeniden bağlan', className: 'bg-rose-500/10 text-rose-600 dark:text-rose-400' },
  unavailable: { label: 'kullanılamıyor', className: 'bg-slate-500/10 text-slate-500 dark:text-slate-400' },
};

export const ConnectedAccountsPage: React.FC = () => {
  const { refresh, activeChannel, selectChannel } = useChannelContext();
  const [connections, setConnections] = useState<PlatformConnection[]>([]);
  const [platforms, setPlatforms] = useState<PlatformDescriptor[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [isAdding, setIsAdding] = useState(false);
  const [granting, setGranting] = useState<string | null>(null);
  const [disconnectTarget, setDisconnectTarget] = useState<PlatformConnection | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [connectionsRes, platformsRes] = await Promise.all([
        apiService.listConnections(false),
        apiService.listPlatforms().catch(() => []),
      ]);
      setConnections(connectionsRes.items);
      setPlatforms(platformsRes);
    } catch (err: any) {
      setError(err?.message || 'Bağlı hesaplar alınamadı.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data?.type === 'TEZLIFY_YOUTUBE_CONNECTED') {
        setIsAdding(false);
        load();
        refresh();
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [load, refresh]);

  const handleAddAccount = async () => {
    setError(null);
    setIsAdding(true);
    try {
      const res = await apiService.connectYouTube('add_account');
      openOAuthPopup(res.auth_url, 'tezlify_youtube_add');
    } catch (err: any) {
      setError(err?.message || 'Yetkilendirme başlatılamadı.');
      setIsAdding(false);
    }
  };

  const handleReconnect = async (connection: PlatformConnection) => {
    setError(null);
    setBusyId(connection.id);
    try {
      const res = await apiService.reconnectConnection(connection.id);
      openOAuthPopup(res.auth_url, `tezlify_youtube_reconnect_${connection.id}`);
    } catch (err: any) {
      setError(err?.message || 'Yeniden bağlanma başlatılamadı.');
    } finally {
      setBusyId(null);
    }
  };

  const handleGrant = async (connection: PlatformConnection, capability: CapabilityName) => {
    setError(null);
    setGranting(`${connection.id}:${capability}`);
    try {
      const result = awaitYouTubeOAuth();
      const res = await apiService.grantCapabilities(connection.id, [capability]);
      openOAuthPopup(res.auth_url, `tezlify_grant_${connection.id}_${capability}`);
      const success = await result;
      await load();
      await refresh();
      if (!success) {
        setError(
          'Ek izin tamamlanmadı. Mevcut hesap bağlantınız ve izinleri korunuyor; işlemi yeniden deneyebilirsiniz.'
        );
      }
    } catch (err: any) {
      setError(err?.message || 'Ek izin başlatılamadı.');
    } finally {
      setGranting(null);
    }
  };

  const handleDisconnectConfirm = async () => {
    if (!disconnectTarget) return;
    setBusyId(disconnectTarget.id);
    try {
      await apiService.disconnectConnection(disconnectTarget.id);
      setDisconnectTarget(null);
      await load();
      await refresh();
    } catch (err: any) {
      setError(err?.message || 'Bağlantı kesilemedi.');
    } finally {
      setBusyId(null);
    }
  };

  const handleToggleChannel = async (channelId: string, enabled: boolean) => {
    setBusyId(channelId);
    try {
      await apiService.setChannelEnabled(channelId, enabled);
      await load();
      await refresh();
    } catch (err: any) {
      setError(err?.message || 'Kanal durumu güncellenemedi.');
    } finally {
      setBusyId(null);
    }
  };

  const youtubeConnections = connections.filter((item) => item.platform === 'youtube');
  const otherPlatforms = platforms.filter((item) => item.id !== 'youtube');

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-bold text-slate-800 dark:text-white">Bağlı Hesaplar</h2>
          <p className="text-xs text-slate-500 dark:text-[#7E7F96]">
            Her Google hesabı ayrı bir bağlantıdır; kanallar bağlantı altında yönetilir.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={load} disabled={isLoading} className="gap-1.5 text-xs">
            {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Yenile
          </Button>
          <Button onClick={handleAddAccount} disabled={isAdding} className="gap-1.5">
            {isAdding ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Hesap Ekle
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-red-500/10">
              <Youtube className="h-4 w-4 text-red-600" />
            </span>
            YouTube
          </CardTitle>
          <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
            Google Hesabı → YouTube kanalları. Bir hesabın birden fazla marka kanalı olabilir.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-10 text-xs text-slate-400">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Hesaplar yükleniyor...
            </div>
          ) : youtubeConnections.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center dark:border-slate-700">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                Bağlı Google hesabı yok
              </p>
              <p className="mt-1 text-xs text-slate-500 dark:text-[#7E7F96]">
                Hesap Ekle ile Google OAuth akışını başlatın. Yetkilendirme sonrası tüm erişilebilir
                kanallar gerçek API verisiyle listelenir.
              </p>
            </div>
          ) : (
            youtubeConnections.map((connection) => {
              const isActive = connection.connection_status === 'active';
              const primaryChannel = connection.channels.find(
                (channel) => channel.is_primary && channel.is_enabled
              );
              return (
                <div
                  key={connection.id}
                  className="overflow-hidden rounded-xl border border-slate-200 dark:border-white/[0.08]"
                >
                  <div className="flex flex-col gap-3 bg-slate-50 p-4 dark:bg-white/[0.03] sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-bold text-slate-800 dark:text-white">
                          {connection.account_display_name}
                        </p>
                        <span
                          className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-bold ${
                            isActive
                              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                              : 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                          }`}
                        >
                          {isActive ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
                          {connection.connection_status}
                        </span>
                        {connection.token_expired && (
                          <span className="rounded-md bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold text-amber-600">
                            token süresi doldu
                          </span>
                        )}
                      </div>
                      <p className="mt-1 font-mono text-[10px] text-slate-400">
                        {connection.account_external_id}
                      </p>
                      <div className="mt-1 flex flex-wrap gap-3 text-[11px] text-slate-500 dark:text-[#7E7F96]">
                        <span>Bağlandı: {formatDate(connection.connected_at)}</span>
                        <span>Son yenileme: {formatDate(connection.last_refreshed_at || connection.connected_at)}</span>
                        <span>{connection.channel_count} kanal</span>
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-wrap items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleReconnect(connection)}
                        disabled={busyId === connection.id}
                        className="gap-1.5 text-xs"
                      >
                        <RefreshCw className={`h-3.5 w-3.5 ${busyId === connection.id ? 'animate-spin' : ''}`} />
                        Yeniden Bağlan
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setDisconnectTarget(connection)}
                        disabled={busyId === connection.id}
                        className="gap-1.5 border-rose-200 text-xs text-rose-600 hover:bg-rose-50 dark:border-rose-900/40 dark:hover:bg-rose-950/20"
                      >
                        <Unplug className="h-3.5 w-3.5" /> Bağlantıyı Kes
                      </Button>
                    </div>
                  </div>

                  <div className="border-t border-slate-100 px-4 py-3 dark:border-white/[0.06]">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-[#7E7F96]">
                      Yetenekler
                    </p>
                    <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {CAPABILITY_ORDER.map((capability) => {
                        const status: CapabilityStatus | undefined = connection.capabilities?.find(
                          (item) => item.capability === capability
                        );
                        const meta = CAPABILITY_META[capability];
                        const state = CAPABILITY_STATE[status?.status || 'unavailable'];
                        const grantKey = `${connection.id}:${capability}`;
                        return (
                          <div
                            key={capability}
                            className="rounded-lg border border-slate-100 p-2.5 dark:border-white/[0.06]"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="min-w-0">
                                <p className="text-[11px] font-bold text-slate-700 dark:text-slate-200">
                                  {meta.label}
                                  {meta.optional && (
                                    <span className="ml-1 text-[9px] font-normal text-slate-400">
                                      isteğe bağlı
                                    </span>
                                  )}
                                </p>
                                <p className="truncate text-[10px] text-slate-400">{meta.description}</p>
                              </div>
                              <span className={`shrink-0 rounded-md px-1.5 py-0.5 text-[9px] font-bold ${state.className}`}>
                                {state.label}
                              </span>
                            </div>
                            {status?.status === 'scope_required' && (
                              <Button
                                variant="outline"
                                size="sm"
                                className="mt-2 h-7 w-full text-[10px]"
                                onClick={() => handleGrant(connection, capability)}
                                disabled={granting === grantKey}
                              >
                                {granting === grantKey && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
                                {meta.grantLabel}
                              </Button>
                            )}
                            {status?.status === 'api_not_enabled' && (
                              <p className="mt-1.5 text-[10px] leading-relaxed text-orange-600 dark:text-orange-400">
                                Google Cloud Console'da YouTube Analytics API etkin değil. İzin vermek bu
                                sorunu çözmez.
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <div className="divide-y divide-slate-100 dark:divide-white/[0.06]">
                    {connection.channels.length === 0 ? (
                      <p className="p-4 text-xs text-slate-400">
                        Bu hesapta erişilebilir kanal bulunmadı. Yeniden bağlanarak kanal listesini tazeleyin.
                      </p>
                    ) : (
                      connection.channels.map((channel) => {
                        const isSelected = channel.id === activeChannel?.id;
                        return (
                          <div key={channel.id} className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:justify-between">
                            <div className="flex min-w-0 items-center gap-3">
                              {channel.avatar_url ? (
                                <img src={channel.avatar_url} alt="" className="h-9 w-9 rounded-full object-cover" />
                              ) : (
                                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-500 dark:bg-white/10">
                                  {channel.channel_name.charAt(0).toUpperCase()}
                                </span>
                              )}
                              <div className="min-w-0">
                                <div className="flex items-center gap-2">
                                  <p className="truncate text-xs font-bold text-slate-800 dark:text-white">
                                    {channel.channel_name}
                                  </p>
                                  {channel.id === primaryChannel?.id && (
                                    <span className="rounded bg-[#7367F0]/10 px-1.5 py-0.5 text-[9px] font-bold text-[#7367F0]">
                                      birincil
                                    </span>
                                  )}
                                  {isSelected && (
                                    <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[9px] font-bold text-emerald-600">
                                      aktif
                                    </span>
                                  )}
                                </div>
                                <p className="truncate font-mono text-[10px] text-slate-400">
                                  {channel.channel_handle || channel.channel_external_id}
                                </p>
                                <p className="text-[10px] text-slate-400">
                                  {channel.subscriber_count.toLocaleString('tr-TR')} abone
                                </p>
                              </div>
                            </div>
                            <div className="flex shrink-0 items-center gap-2">
                              {!isSelected && channel.is_enabled && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-xs"
                                  onClick={() => selectChannel(channel.id)}
                                >
                                  Aktif Yap
                                </Button>
                              )}
                              <label className="flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-[#7E7F96]">
                                <input
                                  type="checkbox"
                                  checked={channel.is_enabled}
                                  disabled={busyId === channel.id}
                                  onChange={(e) => handleToggleChannel(channel.id, e.target.checked)}
                                  className="h-3.5 w-3.5 accent-[#7367F0]"
                                />
                                Yönetimde
                              </label>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      {otherPlatforms.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="h-4 w-4 text-slate-400" /> Diğer Platformlar
            </CardTitle>
            <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
              Bu platformlar için altyapı hazırdır ancak bu sürümde OAuth/API bağlantısı yoktur.
              Aktifmiş gibi gösterilmez ve sahte veri üretilmez.
            </p>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {otherPlatforms.map((platform) => {
              const meta = PLATFORM_META[platform.id] || { label: platform.display_name, color: 'bg-slate-100 text-slate-500' };
              return (
                <div
                  key={platform.id}
                  className="flex items-center justify-between rounded-xl border border-slate-100 p-3 dark:border-white/[0.06]"
                >
                  <div className="flex items-center gap-2">
                    <span className={`flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold ${meta.color}`}>
                      {meta.label.charAt(0)}
                    </span>
                    <div>
                      <p className="text-xs font-bold text-slate-800 dark:text-white">{meta.label}</p>
                      <p className="text-[10px] text-slate-400">Bu sürümde pasif</p>
                    </div>
                  </div>
                  <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500 dark:bg-white/[0.06]">
                    Pasif
                  </span>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[#28C76F]" /> Token ve hesap izolasyonu
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
          <p>
            Her bağlantının erişim ve yenileme tokenı macOS Keychain'de kendi anahtarı altında saklanır
            (<code className="rounded bg-slate-100 px-1 dark:bg-white/10">tezlify.youtube.connection.&lt;id&gt;</code>).
            Token değerleri veritabanına, arayüze veya loglara yazılmaz.
          </p>
          <p className="text-slate-500 dark:text-[#7E7F96]">
            Bir hesabın bağlantısını kesmek diğer hesapları etkilemez. Yalnızca o bağlantıya ait bekleyen
            yükleme ve planlanmış yayınlar güvenli hata durumuna alınır.
          </p>
        </CardContent>
      </Card>

      <ConfirmDialog
        isOpen={Boolean(disconnectTarget)}
        onClose={() => setDisconnectTarget(null)}
        onConfirm={handleDisconnectConfirm}
        title="Hesap Bağlantısını Kes"
        description={`${disconnectTarget?.account_display_name ?? ''} hesabının bağlantısı kaldırılacak. Bu hesaba ait bekleyen yayınlar güvenli şekilde durdurulur. Devam edilsin mi?`}
        confirmLabel="Evet, Bağlantıyı Kes"
        cancelLabel="Vazgeç"
        variant="destructive"
        isLoading={disconnectTarget ? busyId === disconnectTarget.id : false}
      />
    </div>
  );
};
