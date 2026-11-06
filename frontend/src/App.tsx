import React, { lazy, Suspense, useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { Sidebar } from './components/Layout/Sidebar';
import { TopHeader } from './components/Layout/TopHeader';
import { DashboardPage } from './pages/DashboardPage';
import { VideoDetailsModal } from './components/video/VideoDetailsModal';
import { ChannelPublishModal } from './components/youtube/ChannelPublishModal';
import { ConfirmDialog } from './components/ui/ConfirmDialog';
import { useToast } from './components/ui/toast';
import { useTheme } from './hooks/useTheme';
import { ChannelProvider } from './context/ChannelContext';
import { apiService } from './services/api';
import { MediaAsset, SystemStatus } from './types/media';

const GlobalDashboardPage = lazy(() =>
  import('./pages/GlobalDashboardPage').then((m) => ({ default: m.GlobalDashboardPage }))
);
const ChannelOverviewPage = lazy(() =>
  import('./pages/ChannelOverviewPage').then((m) => ({ default: m.ChannelOverviewPage }))
);
const YouTubeVideosPage = lazy(() =>
  import('./pages/YouTubeVideosPage').then((m) => ({ default: m.YouTubeVideosPage }))
);
const PlaylistsPage = lazy(() =>
  import('./pages/PlaylistsPage').then((m) => ({ default: m.PlaylistsPage }))
);
const UploadVideoPage = lazy(() =>
  import('./pages/UploadVideoPage').then((m) => ({ default: m.UploadVideoPage }))
);
const SchedulerPage = lazy(() =>
  import('./pages/SchedulerPage').then((m) => ({ default: m.SchedulerPage }))
);
const AnalyticsPage = lazy(() =>
  import('./pages/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage }))
);
const CommentsPage = lazy(() =>
  import('./pages/CommentsPage').then((m) => ({ default: m.CommentsPage }))
);
const VideoLibraryPage = lazy(() =>
  import('./pages/VideoLibraryPage').then((m) => ({ default: m.VideoLibraryPage }))
);
const ImportVideoPage = lazy(() =>
  import('./pages/ImportVideoPage').then((m) => ({ default: m.ImportVideoPage }))
);
const ConnectedAccountsPage = lazy(() =>
  import('./pages/ConnectedAccountsPage').then((m) => ({ default: m.ConnectedAccountsPage }))
);
const PlatformSettingsPage = lazy(() =>
  import('./pages/PlatformSettingsPage').then((m) => ({ default: m.PlatformSettingsPage }))
);
const ApplicationSettingsPage = lazy(() =>
  import('./pages/ApplicationSettingsPage').then((m) => ({ default: m.ApplicationSettingsPage }))
);

const PageLoader: React.FC = () => (
  <div
    role="status"
    aria-live="polite"
    className="flex items-center justify-center py-24 text-sm text-slate-400 dark:text-slate-500"
  >
    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
    Sayfa yükleniyor...
  </div>
);

type TabId =
  | 'global-dashboard'
  | 'dashboard'
  | 'channel-overview'
  | 'videos'
  | 'playlists'
  | 'upload-video'
  | 'scheduled-videos'
  | 'analytics'
  | 'comments'
  | 'media-library'
  | 'import-video'
  | 'connected-accounts'
  | 'platform-settings'
  | 'app-settings';

export const App: React.FC = () => {
  const { isDark, toggleTheme } = useTheme();
  const { notify } = useToast();

  const [activeTab, setActiveTab] = useState<TabId>('dashboard');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const [videos, setVideos] = useState<MediaAsset[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const [selectedVideo, setSelectedVideo] = useState<MediaAsset | null>(null);
  const [videoToDelete, setVideoToDelete] = useState<MediaAsset | null>(null);
  const [videoToPublish, setVideoToPublish] = useState<MediaAsset | null>(null);
  const [videoToSchedule, setVideoToSchedule] = useState<MediaAsset | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchAllData = async () => {
    setIsLoading(true);
    try {
      const [mediaRes, statusRes] = await Promise.all([
        apiService.listMedia(),
        apiService.getSystemStatus(),
      ]);
      setVideos(mediaRes.items);
      setSystemStatus(statusRes);
      setIsBackendConnected(true);
    } catch (err) {
      console.error('Veri yükleme hatası:', err);
      setIsBackendConnected(false);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
  }, []);

  const handleDeleteConfirm = async () => {
    if (!videoToDelete) return;
    setIsDeleting(true);
    try {
      await apiService.deleteMedia(videoToDelete.id);
      setVideos((prev) => prev.filter((v) => v.id !== videoToDelete.id));
      if (selectedVideo?.id === videoToDelete.id) setSelectedVideo(null);
      setVideoToDelete(null);
    } catch (err: any) {
      notify({
        variant: 'error',
        title: 'Silme işlemi başarısız',
        description: err.message || 'Bilinmeyen hata',
      });
    } finally {
      setIsDeleting(false);
    }
  };

  const getHeaderInfo = () => {
    switch (activeTab) {
      case 'global-dashboard':
        return { title: 'Genel Panel', subtitle: 'Bağlı platformlar, hesaplar, kanallar ve yayın özeti' };
      case 'dashboard':
        return { title: 'Creator Panel', subtitle: 'Kanal durumu, büyüme ve yayın akışı — gerçek verilerle' };
      case 'channel-overview':
        return { title: 'Kanal Özeti', subtitle: 'Bağlı YouTube kanalı profili ve oynatma listeleri' };
      case 'videos':
        return { title: 'Videolar', subtitle: 'Kanal videoları, meta veri düzenleme ve gizlilik yönetimi' };
      case 'playlists':
        return { title: 'Oynatma Listeleri', subtitle: 'Kanal oynatma listeleri, video ekleme ve düzenleme' };
      case 'upload-video':
        return { title: 'Video Yükle', subtitle: 'Yerel medyayı YouTube resumable upload ile yayınlama' };
      case 'scheduled-videos':
        return { title: 'Planlanan Videolar', subtitle: 'İleri tarihli yayınlar, takvim ve arka plan zamanlayıcısı' };
      case 'analytics':
        return { title: 'Analitik', subtitle: 'YouTube Analytics API: görüntüleme, izlenme, abone ve kırılımlar' };
      case 'comments':
        return { title: 'Yorumlar', subtitle: 'Kanal yorumları, yanıtlar ve moderasyon' };
      case 'media-library':
        return { title: 'Yerel Medya Kütüphanesi', subtitle: `${videos.length} yerel video · yükleme ve planlama için hazır` };
      case 'import-video':
        return { title: 'Video İçe Aktar', subtitle: 'Bilgisayarınızdan yerel diske video aktarma ve analiz' };
      case 'connected-accounts':
        return { title: 'Bağlı Hesaplar', subtitle: 'YouTube OAuth bağlantısı ve Keychain token güvenliği' };
      case 'platform-settings':
        return { title: 'Platform Ayarları', subtitle: 'Platform yetenekleri ve kapsam gereksinimleri' };
      case 'app-settings':
        return { title: 'Uygulama Ayarları', subtitle: 'Yerel ortam, araçlar ve depolama bilgileri' };
      default:
        return { title: 'Tezlify Creator Studio' };
    }
  };

  const headerInfo = getHeaderInfo();
  const navigate = (tab: string) => setActiveTab(tab as TabId);

  return (
    <ChannelProvider>
    <div className="flex h-screen overflow-hidden bg-[#F8F7FA] dark:bg-[#25293C] text-[#4B465C] dark:text-[#DBD7EC]">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[110] focus:rounded-lg focus:bg-[#7367F0] focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white"
      >
        İçeriğe geç
      </a>
      <Sidebar
        activeTab={activeTab}
        setActiveTab={navigate}
        isBackendConnected={isBackendConnected}
        totalVideosCount={videos.length}
        isOpenMobile={isMobileMenuOpen}
        onCloseMobile={() => setIsMobileMenuOpen(false)}
      />

      <div className="app-scroll flex-1 flex flex-col min-w-0 overflow-y-auto">
        <TopHeader
          title={headerInfo.title}
          subtitle={headerInfo.subtitle}
          isDark={isDark}
          onToggleTheme={toggleTheme}
          onToggleMobileMenu={() => setIsMobileMenuOpen(true)}
          onQuickUpload={() => setActiveTab('upload-video')}
          onManageAccounts={() => setActiveTab('connected-accounts')}
        />

        <main
          key={activeTab}
          id="main-content"
          tabIndex={-1}
          className="page-enter flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto focus:outline-none"
        >
          <Suspense fallback={<PageLoader />}>
          {activeTab === 'global-dashboard' && <GlobalDashboardPage onNavigate={navigate} />}

          {activeTab === 'dashboard' && <DashboardPage onNavigate={navigate} />}

          {activeTab === 'channel-overview' && <ChannelOverviewPage onNavigate={navigate} />}

          {activeTab === 'videos' && <YouTubeVideosPage />}

          {activeTab === 'playlists' && <PlaylistsPage />}

          {activeTab === 'upload-video' && (
            <UploadVideoPage
              videos={videos}
              onNavigateLibrary={() => setActiveTab('media-library')}
              onNavigateAccounts={() => setActiveTab('connected-accounts')}
            />
          )}

          {activeTab === 'scheduled-videos' && (
            <SchedulerPage
              videos={videos}
              initialAssetToSchedule={videoToSchedule}
              onClearInitialAsset={() => setVideoToSchedule(null)}
            />
          )}

          {activeTab === 'analytics' && <AnalyticsPage onNavigate={navigate} />}

          {activeTab === 'comments' && <CommentsPage />}

          {activeTab === 'media-library' && (
            <VideoLibraryPage
              videos={videos}
              isLoading={isLoading}
              onSelectVideo={(asset) => setSelectedVideo(asset)}
              onRequestDelete={(asset) => setVideoToDelete(asset)}
              onNavigateImport={() => setActiveTab('import-video')}
              onPublishVideo={(asset) => setVideoToPublish(asset)}
              onScheduleVideo={(asset) => {
                setVideoToSchedule(asset);
                setActiveTab('scheduled-videos');
              }}
            />
          )}

          {activeTab === 'import-video' && (
            <ImportVideoPage
              onUploadSuccess={(newAsset) => setVideos((prev) => [newAsset, ...prev])}
              onViewVideo={(asset) => setSelectedVideo(asset)}
            />
          )}

          {activeTab === 'connected-accounts' && <ConnectedAccountsPage />}

          {activeTab === 'platform-settings' && <PlatformSettingsPage />}

          {activeTab === 'app-settings' && (
            <ApplicationSettingsPage systemStatus={systemStatus} onRefreshStatus={fetchAllData} />
          )}
          </Suspense>
        </main>
      </div>

      <VideoDetailsModal
        asset={selectedVideo}
        isOpen={Boolean(selectedVideo)}
        onClose={() => setSelectedVideo(null)}
        onDeleteRequest={(asset) => {
          setSelectedVideo(null);
          setVideoToDelete(asset);
        }}
        onPublishRequest={(asset) => {
          setSelectedVideo(null);
          setVideoToPublish(asset);
        }}
      />

      <ChannelPublishModal
        asset={videoToPublish}
        isOpen={Boolean(videoToPublish)}
        onClose={() => setVideoToPublish(null)}
        onPublishStarted={() => {
          setVideoToPublish(null);
          setActiveTab('upload-video');
        }}
      />

      <ConfirmDialog
        isOpen={Boolean(videoToDelete)}
        onClose={() => setVideoToDelete(null)}
        onConfirm={handleDeleteConfirm}
        title="Videoyu Silmek İstediğinize Emin Misiniz?"
        description={`"${videoToDelete?.original_filename}" dosyası ve veritabanı kaydı kalıcı olarak silinecektir. Bu işlem geri alınamaz.`}
        confirmLabel="Evet, Kalıcı Olarak Sil"
        cancelLabel="Vazgeç"
        variant="destructive"
        isLoading={isDeleting}
      />
    </div>
    </ChannelProvider>
  );
};
