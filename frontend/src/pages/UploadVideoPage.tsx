import React, { useState, useEffect, useCallback } from 'react';
import { MediaAsset } from '../types/media';
import { PublishRecord } from '../types/publish';
import { apiService } from '../services/api';
import { useChannelContext } from '../context/ChannelContext';
import { PublishProgressCard } from '../components/youtube/PublishProgressCard';
import { PublishHistoryTable } from '../components/youtube/PublishHistoryTable';
import { YouTubePublishModal } from '../components/youtube/YouTubePublishModal';
import { Button } from '../components/ui/button';
import { Spinner } from '../components/ui/Spinner';
import { Youtube, Link2, AlertTriangle, ShieldAlert } from 'lucide-react';
import {
  CAPABILITY_META,
  capabilityAllows,
  capabilityNeedsScope,
  findCapability,
} from '../lib/capabilities';
import { awaitYouTubeOAuth, openOAuthPopup } from '../lib/youtubeOAuth';

interface UploadVideoPageProps {
  videos: MediaAsset[];
  onNavigateLibrary: () => void;
  onNavigateAccounts: () => void;
}

export const UploadVideoPage: React.FC<UploadVideoPageProps> = ({
  videos,
  onNavigateLibrary,
  onNavigateAccounts,
}) => {
  const {
    activeChannel,
    connections,
    isLoading: isChannelLoading,
    refresh,
  } = useChannelContext();
  const channelId = activeChannel?.id;

  const [publishRecords, setPublishRecords] = useState<PublishRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isGrantingUpload, setIsGrantingUpload] = useState(false);

  const [isPublishModalOpen, setIsPublishModalOpen] = useState(false);
  const [selectedVideoForPublish, setSelectedVideoForPublish] = useState<MediaAsset | null>(null);

  const fetchHistory = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const res = await apiService.listPublishRecords(50, 0, channelId);
      setPublishRecords(res.items);
    } catch (err: any) {
      setLoadError(err.message || 'Yayın geçmişi yüklenemedi.');
    } finally {
      setIsLoading(false);
    }
  }, [channelId]);

  useEffect(() => {
    setPublishRecords([]);
    if (channelId) fetchHistory();
    else setIsLoading(false);
  }, [channelId, fetchHistory]);

  const connection = connections.find((item) => item.id === activeChannel?.platform_connection_id);
  const uploadAllowed = capabilityAllows(connection, 'upload');
  const uploadNeedsScope = capabilityNeedsScope(connection, 'upload');
  const uploadStatus = findCapability(connection, 'upload');

  const handleStartPublishFromSelect = (asset: MediaAsset) => {
    if (!uploadAllowed) {
      setLoadError(
        'YouTube yükleme izni olmadan yayın başlatılamaz. Önce "YouTube yükleme izni ver" ile izin verin.'
      );
      return;
    }
    setSelectedVideoForPublish(asset);
    setIsPublishModalOpen(true);
  };

  const handleGrantUpload = async () => {
    if (!connection) return;
    setIsGrantingUpload(true);
    setLoadError(null);
    try {
      const result = awaitYouTubeOAuth();
      const res = await apiService.grantCapabilities(connection.id, ['upload']);
      openOAuthPopup(res.auth_url, `tezlify_grant_upload_${connection.id}`);
      const success = await result;
      await refresh();
      if (!success) {
        setLoadError(
          'Yükleme izni verilmedi. Mevcut hesap bağlantınız korunuyor; izin vermeden yayın başlatılamaz.'
        );
      }
    } catch (err: any) {
      setLoadError(err?.message || 'Yükleme izni başlatılamadı.');
    } finally {
      setIsGrantingUpload(false);
    }
  };

  const handlePublishStarted = (newRecord: PublishRecord) => {
    setPublishRecords((prev) => [newRecord, ...prev]);
  };

  const handleRecordUpdated = (updated: PublishRecord) => {
    setPublishRecords((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
  };

  const activeRecords = publishRecords.filter((r) =>
    ['pending', 'authenticating', 'uploading', 'paused', 'processing'].includes(r.status)
  );

  if (isChannelLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-xs text-slate-400">
        <Spinner size="sm" /> <span className="ml-2">Kanal bilgisi yükleniyor...</span>
      </div>
    );
  }

  if (!activeChannel) {
    return (
      <div className="p-8 rounded-xl bg-white dark:bg-[#2F3349] border border-slate-200/80 dark:border-slate-800 text-center space-y-4">
        <div className="w-16 h-16 mx-auto rounded-2xl bg-red-500/10 flex items-center justify-center text-red-600 dark:text-red-400">
          <Youtube className="w-8 h-8" />
        </div>
        <div className="max-w-md mx-auto space-y-2">
          <h3 className="text-base font-semibold text-[#4B465C] dark:text-[#DBD7EC]">
            Yükleme için kanal seçili değil
          </h3>
          <p className="text-xs text-[#828092] dark:text-[#908DA1] leading-relaxed">
            YouTube kanalınızı bağlayın veya yönetim ekranından etkin bir kanal seçin. Yükleme hedefi her zaman
            seçili kanalın bağlantısına göre belirlenir.
          </p>
        </div>
        <Button size="sm" onClick={onNavigateAccounts} className="gap-2">
          <Link2 className="h-4 w-4" /> Bağlı Hesaplar
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Active target channel banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-white dark:bg-[#2F3349] border border-slate-200/80 dark:border-slate-800 shadow-sm">
        <div className="flex items-center gap-3 min-w-0">
          {activeChannel.avatar_url ? (
            <img
              src={activeChannel.avatar_url}
              alt={activeChannel.channel_name}
              className="h-11 w-11 rounded-full object-cover border border-slate-200 dark:border-white/10"
            />
          ) : (
            <div className="h-11 w-11 rounded-full bg-[#7367F0]/10 text-[#7367F0] flex items-center justify-center">
              <Youtube className="h-5 w-5" />
            </div>
          )}
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-wider text-[#7367F0]">Hedef Kanal</p>
            <p className="truncate text-sm font-semibold text-[#4B465C] dark:text-[#DBD7EC]">
              {activeChannel.channel_name}
            </p>
            <p className="truncate text-[11px] text-[#828092] dark:text-[#908DA1]">
              {activeChannel.channel_handle || activeChannel.channel_external_id}
              {connection ? ` · ${connection.account_display_name}` : ''}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-[#28C76F]/10 px-2.5 py-1 text-[11px] font-bold text-[#28C76F]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#28C76F]" />
            Bağlantı: {connection?.connection_status || activeChannel.connection_status}
          </span>
          <Button variant="outline" size="sm" onClick={onNavigateAccounts} className="text-xs gap-1.5">
            <Link2 className="h-3.5 w-3.5" /> Kanal Değiştir
          </Button>
        </div>
      </div>

      {/* Missing upload permission */}
      {!uploadAllowed && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-500/20 dark:bg-amber-500/10">
          <div className="flex items-start gap-3">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
            <div className="min-w-0 space-y-1.5">
              <h3 className="text-sm font-semibold text-amber-900 dark:text-amber-200">
                YouTube yükleme izni gerekiyor
              </h3>
              <p className="text-xs leading-relaxed text-amber-800 dark:text-amber-300">
                {uploadStatus?.status === 'api_not_enabled'
                  ? 'YouTube Data API projenizde etkin değil. Google Cloud Console üzerinden YouTube Data API v3 servisini etkinleştirdikten sonra tekrar deneyin.'
                  : uploadStatus?.status === 'reauth_required' || uploadStatus?.status === 'unavailable'
                    ? 'Seçili hesabın bağlantısı yeniden yetkilendirme gerektiriyor. Mevcut bağlantı korunur; Bağlı Hesaplar ekranından bağlantıyı yenileyin.'
                    : 'Mevcut hesap bağlantınız yalnızca temel okuma izinlerine sahip. Yayın başlatmadan önce yalnızca yükleme yeteneğini ekleyebilirsiniz; mevcut izinler ve token\'lar korunur.'}
              </p>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                {uploadNeedsScope && (
                  <Button size="sm" onClick={handleGrantUpload} disabled={isGrantingUpload} className="gap-2">
                    {isGrantingUpload ? <Spinner size="sm" /> : <Youtube className="h-4 w-4" />}
                    YouTube yükleme izni ver
                  </Button>
                )}
                {(uploadStatus?.status === 'reauth_required' ||
                  uploadStatus?.status === 'unavailable' ||
                  uploadStatus?.status === 'api_not_enabled') && (
                  <Button variant="outline" size="sm" onClick={onNavigateAccounts} className="gap-2">
                    <Link2 className="h-4 w-4" /> Bağlı Hesaplar
                  </Button>
                )}
                <span className="text-[11px] text-amber-700 dark:text-amber-400">
                  {CAPABILITY_META.upload.label} · {uploadStatus?.status ?? 'unavailable'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Upload entry */}
      {uploadAllowed && (
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-white dark:bg-[#2F3349] border border-slate-200/80 dark:border-slate-800 shadow-sm">
        <div>
          <h3 className="text-sm font-semibold text-[#4B465C] dark:text-[#DBD7EC]">
            Yerel videoyu bu kanala yükle
          </h3>
          <p className="text-xs text-[#828092] dark:text-[#908DA1] mt-0.5">
            Kütüphanenizden bir video seçin; başlık, açıklama, etiket, kategori, kapak ve gizlilik bilgilerini
            girip resumable yükleme başlatın. Yükleme yalnızca <strong>{activeChannel.channel_name}</strong>{' '}
            kanalına gönderilir.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {videos.length > 0 ? (
            <select
              className="text-xs px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#25293C] border border-slate-200 dark:border-slate-700 text-[#4B465C] dark:text-[#DBD7EC] focus:outline-none focus:ring-1 focus:ring-[#7367F0]"
              onChange={(e) => {
                const v = videos.find((item) => item.id === e.target.value);
                if (v) handleStartPublishFromSelect(v);
                e.target.value = '';
              }}
              defaultValue=""
            >
              <option value="" disabled>
                Kütüphaneden Video Seç...
              </option>
              {videos.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.original_filename}
                </option>
              ))}
            </select>
          ) : (
            <Button variant="outline" size="sm" onClick={onNavigateLibrary} className="text-xs">
              Önce Video Yükleyin
            </Button>
          )}
        </div>
      </div>
      )}

      {loadError && (
        <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{loadError}</span>
        </div>
      )}

      {activeRecords.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-[#4B465C] dark:text-[#DBD7EC] flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
            Devam Eden Yüklemeler ({activeRecords.length})
          </h3>
          <div className="space-y-3">
            {activeRecords.map((r) => (
              <PublishProgressCard key={r.id} initialRecord={r} onRecordUpdated={handleRecordUpdated} />
            ))}
          </div>
        </div>
      )}

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-[#4B465C] dark:text-[#DBD7EC]">Yayınlama Geçmişi</h3>
            <p className="text-[11px] text-[#828092] dark:text-[#908DA1] mt-0.5">
              Yalnızca seçili kanala ait yayın kayıtları gösterilir.
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchHistory}
            disabled={isLoading}
            className="text-xs text-[#828092] hover:text-[#4B465C]"
          >
            {isLoading ? <Spinner size="sm" /> : 'Yenile'}
          </Button>
        </div>

        <PublishHistoryTable
          records={publishRecords}
          onResume={(record: PublishRecord) => {
            apiService.resumePublish(record.id).then(fetchHistory);
          }}
          isLoading={isLoading}
        />
      </div>

      <YouTubePublishModal
        asset={selectedVideoForPublish}
        isOpen={isPublishModalOpen}
        onClose={() => {
          setIsPublishModalOpen(false);
          setSelectedVideoForPublish(null);
        }}
        onPublishStarted={handlePublishStarted}
        channelId={channelId || null}
        channelName={activeChannel.channel_name}
        playlistWriteAllowed={capabilityAllows(connection, 'comments')}
      />
    </div>
  );
};
