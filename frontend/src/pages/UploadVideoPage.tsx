import React, { useState, useEffect, useCallback } from 'react';
import { MediaAsset } from '../types/media';
import { SocialAccount, PublishRecord } from '../types/publish';
import { apiService } from '../services/api';
import { YouTubeConnectionCard } from '../components/youtube/YouTubeConnectionCard';
import { PublishProgressCard } from '../components/youtube/PublishProgressCard';
import { PublishHistoryTable } from '../components/youtube/PublishHistoryTable';
import { YouTubePublishModal } from '../components/youtube/YouTubePublishModal';
import { Button } from '../components/ui/button';
import { Spinner } from '../components/ui/Spinner';

interface UploadVideoPageProps {
  videos: MediaAsset[];
  onNavigateLibrary: () => void;
}

export const UploadVideoPage: React.FC<UploadVideoPageProps> = ({
  videos,
  onNavigateLibrary,
}) => {
  const [account, setAccount] = useState<SocialAccount | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [publishRecords, setPublishRecords] = useState<PublishRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Modal for publishing
  const [isPublishModalOpen, setIsPublishModalOpen] = useState(false);
  const [selectedVideoForPublish, setSelectedVideoForPublish] = useState<MediaAsset | null>(null);

  const fetchStatusAndHistory = useCallback(async () => {
    setIsLoading(true);
    try {
      const [statusRes, historyRes] = await Promise.all([
        apiService.getYouTubeStatus(),
        apiService.listPublishRecords(50, 0),
      ]);
      setIsConnected(statusRes.connected);
      setAccount(statusRes.account);
      setPublishRecords(historyRes.items);
    } catch (err) {
      console.error('Failed to fetch YouTube status/history:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatusAndHistory();
  }, [fetchStatusAndHistory]);

  const handleStartPublishFromSelect = (asset: MediaAsset) => {
    setSelectedVideoForPublish(asset);
    setIsPublishModalOpen(true);
  };

  const handlePublishStarted = (newRecord: PublishRecord) => {
    setPublishRecords((prev) => [newRecord, ...prev]);
  };

  const handleRecordUpdated = (updated: PublishRecord) => {
    setPublishRecords((prev) =>
      prev.map((r) => (r.id === updated.id ? updated : r))
    );
  };

  // Filter active uploads vs historical
  const activeRecords = publishRecords.filter((r) =>
    ['pending', 'authenticating', 'uploading', 'paused', 'processing'].includes(r.status)
  );

  return (
    <div className="space-y-6">
      {/* YouTube Connection Status Banner / Card */}
      <YouTubeConnectionCard
        account={account}
        isConnected={isConnected}
        onAccountChange={fetchStatusAndHistory}
      />

      {/* Main Content Area */}
      {isConnected ? (
        <div className="space-y-6">
          {/* Header Action: Quick Select Video to Publish */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-white dark:bg-[#2F3349] border border-slate-200/80 dark:border-slate-800 shadow-sm">
            <div>
              <h3 className="text-sm font-semibold text-[#4B465C] dark:text-[#DBD7EC]">
                Yerel videoyu YouTube'a yükle
              </h3>
              <p className="text-xs text-[#828092] dark:text-[#908DA1] mt-0.5">
                Kütüphanenizdeki bir videoyu seçin; başlık, açıklama, etiket, kategori, kapak ve gizlilik bilgilerini girip resumable yükleme başlatın. İleri tarihli yayın için Yayın Takvimi sayfasını kullanın.
              </p>
            </div>

            <div className="flex items-center gap-3">
              {videos.length > 0 ? (
                <div className="flex items-center gap-2">
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
                </div>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onNavigateLibrary}
                  className="text-xs"
                >
                  Önce Video Yükleyin
                </Button>
              )}
            </div>
          </div>

          {/* Active Uploads / In-Progress Tasks */}
          {activeRecords.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-[#4B465C] dark:text-[#DBD7EC] flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
                Devam Eden Yüklemeler ({activeRecords.length})
              </h3>
              <div className="space-y-3">
                {activeRecords.map((r) => (
                  <PublishProgressCard
                    key={r.id}
                    initialRecord={r}
                    onRecordUpdated={handleRecordUpdated}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Publishing History */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-[#4B465C] dark:text-[#DBD7EC]">
                Yayınlama Geçmişi
              </h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={fetchStatusAndHistory}
                disabled={isLoading}
                className="text-xs text-[#828092] hover:text-[#4B465C]"
              >
                {isLoading ? <Spinner size="sm" /> : 'Yenile'}
              </Button>
            </div>

            <PublishHistoryTable
              records={publishRecords}
              onResume={(record: PublishRecord) => {
                // Resume upload
                apiService.resumePublish(record.id).then(fetchStatusAndHistory);
              }}
              isLoading={isLoading}
            />
          </div>
        </div>
      ) : (
        <div className="p-8 rounded-xl bg-white dark:bg-[#2F3349] border border-slate-200/80 dark:border-slate-800 text-center space-y-4">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-red-500/10 flex items-center justify-center text-red-600 dark:text-red-400">
            <svg className="w-8 h-8" viewBox="0 0 24 24" fill="currentColor">
              <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
            </svg>
          </div>
          <div className="max-w-md mx-auto space-y-2">
            <h3 className="text-base font-semibold text-[#4B465C] dark:text-[#DBD7EC]">
              YouTube Yayınlama Modülü
            </h3>
            <p className="text-xs text-[#828092] dark:text-[#908DA1] leading-relaxed">
              Google OAuth 2.0 PKCE desktop yetkilendirmesi ile doğrudan YouTube kanalınızı bağlayın.
              Tokenlarınız sisteminizdeki <strong>macOS Keychain</strong> içinde şifreli saklanır ve sunucuya veya tarayıcıya asla açık aktarılmaz.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-50 dark:bg-[#25293C] text-[11px] text-[#828092] font-mono border border-slate-200 dark:border-slate-700">
            <span>Protokol: Google Resumable Upload (308 Incomplete)</span>
          </div>
        </div>
      )}

      {/* Publish Video Modal */}
      <YouTubePublishModal
        asset={selectedVideoForPublish}
        isOpen={isPublishModalOpen}
        onClose={() => {
          setIsPublishModalOpen(false);
          setSelectedVideoForPublish(null);
        }}
        onPublishStarted={handlePublishStarted}
      />
    </div>
  );
};
