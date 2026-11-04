import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Layout/Sidebar';
import { TopHeader } from './components/Layout/TopHeader';
import { StudioWorkspacePage } from './pages/StudioWorkspacePage';
import { VideoLibraryPage } from './pages/VideoLibraryPage';
import { ImportVideoPage } from './pages/ImportVideoPage';
import { SettingsPage } from './pages/SettingsPage';
import { YouTubePublisherPage } from './pages/YouTubePublisherPage';
import { SchedulerPage } from './pages/SchedulerPage';
import { CharacterStudioPage } from './pages/CharacterStudioPage';
import { CompositionStudioPage } from './pages/CompositionStudioPage';
import { VideoDetailsModal } from './components/video/VideoDetailsModal';
import { YouTubePublishModal } from './components/youtube/YouTubePublishModal';
import { ConfirmDialog } from './components/ui/ConfirmDialog';
import { useTheme } from './hooks/useTheme';
import { apiService } from './services/api';
import { MediaAsset, SystemStatus } from './types/media';
import { RenderJob, StudioProject } from './types/studio';

export const App: React.FC = () => {
  const { isDark, toggleTheme } = useTheme();

  const [activeTab, setActiveTab] = useState<
    'studio' | 'media-library' | 'import-video' | 'youtube-publisher' | 'scheduler' | 'character-studio' | 'composition-studio' | 'settings'
  >('studio');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const [videos, setVideos] = useState<MediaAsset[]>([]);
  const [studioRenders, setStudioRenders] = useState<RenderJob[]>([]);
  const [studioProjects, setStudioProjects] = useState<StudioProject[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Modals state
  const [selectedVideo, setSelectedVideo] = useState<MediaAsset | null>(null);
  const [videoToDelete, setVideoToDelete] = useState<MediaAsset | null>(null);
  const [videoToPublish, setVideoToPublish] = useState<MediaAsset | null>(null);
  const [videoToSchedule, setVideoToSchedule] = useState<MediaAsset | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchAllData = async () => {
    setIsLoading(true);
    try {
      const [mediaRes, statusRes, renderRes, projectRes] = await Promise.all([
        apiService.listMedia(),
        apiService.getSystemStatus(),
        apiService.listRenderJobs(200, 0).catch(() => ({ items: [] as RenderJob[], total: 0 })),
        apiService.listProjects(100, 0).catch(() => ({
          items: [] as StudioProject[],
          total: 0,
          limit: 100,
          offset: 0,
        })),
      ]);
      setVideos(mediaRes.items);
      setSystemStatus(statusRes);
      setStudioRenders(renderRes.items);
      setStudioProjects(projectRes.items);
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

  // Studio outputs are created while the user is in the AI Studio tab. Refresh
  // the render history when the media library is opened so cards never go stale.
  useEffect(() => {
    if (activeTab !== 'media-library') return;
    let active = true;
    Promise.all([
      apiService.listRenderJobs(200, 0).catch(() => null),
      apiService.listProjects(100, 0).catch(() => null),
    ]).then(([renderRes, projectRes]) => {
      if (!active) return;
      if (renderRes) setStudioRenders(renderRes.items);
      if (projectRes) setStudioProjects(projectRes.items);
    });
    return () => {
      active = false;
    };
  }, [activeTab]);

  const handleDeleteConfirm = async () => {
    if (!videoToDelete) return;
    setIsDeleting(true);
    try {
      await apiService.deleteMedia(videoToDelete.id);
      setVideos((prev) => prev.filter((v) => v.id !== videoToDelete.id));
      if (selectedVideo?.id === videoToDelete.id) {
        setSelectedVideo(null);
      }
      setVideoToDelete(null);
    } catch (err: any) {
      alert(`Silme işlemi başarısız: ${err.message || 'Bilinmeyen hata'}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const getHeaderInfo = () => {
    switch (activeTab) {
      case 'studio':
        return {
          title: 'AI Video Studio',
          subtitle: 'Proje, hikâye, karakter, sahne, animasyon ve dışa aktarma akışı',
        };
      case 'media-library':
        return {
          title: 'Medya Kütüphanesi',
          subtitle: `${videos.length} yüklenen medya · ${studioRenders.length} Studio çıktısı`,
        };
      case 'import-video':
        return {
          title: 'Video İçe Aktar',
          subtitle: 'Bilgisayarınızdan yerel diske video yükleme ve analiz',
        };
      case 'youtube-publisher':
        return {
          title: 'YouTube Publisher',
          subtitle: 'Google OAuth 2.0 PKCE ve Resumable Upload ile YouTube yayını',
        };
      case 'scheduler':
        return {
          title: 'YouTube Yayın Takvimi',
          subtitle: 'Arka plan zamanlayıcısı ile otomatik ileri tarihli video yayını',
        };
      case 'character-studio':
        return {
          title: 'Karakter & Animasyon Stüdyosu',
          subtitle: 'Gelişmiş karakter, asset ve Blender render araçları',
        };
      case 'composition-studio':
        return {
          title: 'Video Kompozisyon Stüdyosu',
          subtitle: 'Gelişmiş sahne birleştirme, geçişler, Türkçe metin/altyazı ve çok formatlı MP4 çıktısı',
        };
      case 'settings':
        return {
          title: 'Sistem Durumu ve Ayarlar',
          subtitle: 'Ortam, araçlar ve disk depolama bilgileri',
        };
      default:
        return { title: 'Tezlify AI Video Studio' };
    }
  };

  const headerInfo = getHeaderInfo();

  return (
    <div className="flex h-screen overflow-hidden bg-[#F8F7FA] dark:bg-[#25293C] text-[#4B465C] dark:text-[#DBD7EC]">
      {/* Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={(tab: string) => setActiveTab(tab as any)}
        isBackendConnected={isBackendConnected}
        totalVideosCount={videos.length}
        isOpenMobile={isMobileMenuOpen}
        onCloseMobile={() => setIsMobileMenuOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <TopHeader
          title={headerInfo.title}
          subtitle={headerInfo.subtitle}
          isDark={isDark}
          onToggleTheme={toggleTheme}
          onToggleMobileMenu={() => setIsMobileMenuOpen(true)}
          onQuickUpload={() => setActiveTab('import-video')}
        />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          {activeTab === 'studio' && (
            <StudioWorkspacePage
              onOpenMediaLibrary={() => setActiveTab('media-library')}
              onOpenCharacterStudio={() => setActiveTab('character-studio')}
            />
          )}

          {activeTab === 'media-library' && (
            <VideoLibraryPage
              videos={videos}
              isLoading={isLoading}
              studioRenders={studioRenders}
              studioProjects={studioProjects}
              onOpenProject={(projectId) => {
                localStorage.setItem('tezlify.studio.project', projectId);
                localStorage.setItem('tezlify.studio.view', 'workflow');
                setActiveTab('studio');
              }}
              onSelectVideo={(asset) => setSelectedVideo(asset)}
              onRequestDelete={(asset) => setVideoToDelete(asset)}
              onNavigateImport={() => setActiveTab('import-video')}
              onPublishVideo={(asset) => setVideoToPublish(asset)}
              onScheduleVideo={(asset) => {
                setVideoToSchedule(asset);
                setActiveTab('scheduler');
              }}
            />
          )}

          {activeTab === 'import-video' && (
            <ImportVideoPage
              onUploadSuccess={(newAsset) => {
                setVideos((prev) => [newAsset, ...prev]);
              }}
              onViewVideo={(asset) => {
                setSelectedVideo(asset);
              }}
            />
          )}

          {activeTab === 'youtube-publisher' && (
            <YouTubePublisherPage
              videos={videos}
              onNavigateLibrary={() => setActiveTab('media-library')}
            />
          )}

          {activeTab === 'scheduler' && (
            <SchedulerPage
              videos={videos}
              initialAssetToSchedule={videoToSchedule}
              onClearInitialAsset={() => setVideoToSchedule(null)}
            />
          )}

          {activeTab === 'character-studio' && (
            <CharacterStudioPage />
          )}

          {activeTab === 'composition-studio' && (
            <CompositionStudioPage />
          )}

          {activeTab === 'settings' && (
            <SettingsPage
              systemStatus={systemStatus}
              onRefreshStatus={fetchAllData}
            />
          )}
        </main>
      </div>

      {/* Video Details & HTML5 Player Modal */}
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

      {/* YouTube Publish Modal */}
      <YouTubePublishModal
        asset={videoToPublish}
        isOpen={Boolean(videoToPublish)}
        onClose={() => setVideoToPublish(null)}
        onPublishStarted={() => {
          setVideoToPublish(null);
          setActiveTab('youtube-publisher');
        }}
      />

      {/* Safe Delete Confirmation Dialog */}
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
  );
};
