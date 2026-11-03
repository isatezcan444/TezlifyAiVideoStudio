import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Layout/Sidebar';
import { TopHeader } from './components/Layout/TopHeader';
import { DashboardPage } from './pages/DashboardPage';
import { VideoLibraryPage } from './pages/VideoLibraryPage';
import { ImportVideoPage } from './pages/ImportVideoPage';
import { SettingsPage } from './pages/SettingsPage';
import { VideoDetailsModal } from './components/video/VideoDetailsModal';
import { ConfirmDialog } from './components/ui/ConfirmDialog';
import { useTheme } from './hooks/useTheme';
import { apiService } from './services/api';
import { MediaAsset, SystemStatus } from './types/media';

export const App: React.FC = () => {
  const { isDark, toggleTheme } = useTheme();

  const [activeTab, setActiveTab] = useState<'dashboard' | 'media-library' | 'import-video' | 'settings'>('dashboard');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const [videos, setVideos] = useState<MediaAsset[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Modals state
  const [selectedVideo, setSelectedVideo] = useState<MediaAsset | null>(null);
  const [videoToDelete, setVideoToDelete] = useState<MediaAsset | null>(null);
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
      case 'dashboard':
        return {
          title: 'Kontrol Paneli (Dashboard)',
          subtitle: 'Video üretim ve medya yönetimi genel görünümü',
        };
      case 'media-library':
        return {
          title: 'Medya Kütüphanesi',
          subtitle: `${videos.length} adet doğrulanmış video kaydı`,
        };
      case 'import-video':
        return {
          title: 'Video İçe Aktar',
          subtitle: 'Bilgisayarınızdan yerel diske video yükleme ve analiz',
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
          {activeTab === 'dashboard' && (
            <DashboardPage
              videos={videos}
              systemStatus={systemStatus}
              isLoading={isLoading}
              onNavigateTab={(tab) => setActiveTab(tab as any)}
              onSelectVideo={(asset) => setSelectedVideo(asset)}
            />
          )}

          {activeTab === 'media-library' && (
            <VideoLibraryPage
              videos={videos}
              isLoading={isLoading}
              onSelectVideo={(asset) => setSelectedVideo(asset)}
              onRequestDelete={(asset) => setVideoToDelete(asset)}
              onNavigateImport={() => setActiveTab('import-video')}
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

