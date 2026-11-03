import React from 'react';
import { StatsCard } from '../components/ui/StatsCard';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { MediaAsset, SystemStatus } from '../types/media';
import { formatBytes, formatDuration, formatDate } from '../lib/utils';
import { StatusBadge } from '../components/ui/StatusBadge';
import {
  Film,
  HardDrive,
  Clock,
  Activity,
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  Play,
  ArrowRight,
  Server,
} from 'lucide-react';

interface DashboardPageProps {
  videos: MediaAsset[];
  systemStatus: SystemStatus | null;
  isLoading: boolean;
  onNavigateTab: (tab: string) => void;
  onSelectVideo: (asset: MediaAsset) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  videos,
  systemStatus,
  isLoading,
  onNavigateTab,
  onSelectVideo,
}) => {
  const totalDuration = videos.reduce((acc, v) => acc + (v.metadata?.duration_seconds || 0), 0);
  const totalStorage = videos.reduce((acc, v) => acc + v.file_size_bytes, 0);

  return (
    <div className="space-y-6">
      {/* Top Welcome / Hero Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-[#7367F0] via-[#867BFF] to-[#9E95F5] p-6 sm:p-8 text-white shadow-xl shadow-[#7367F0]/20">
        <div className="relative z-10 max-w-2xl space-y-2">
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-white/20 backdrop-blur-md text-xs font-bold text-white">
            <span className="w-2 h-2 rounded-full bg-[#28C76F]" />
            <span>Local-First Studio Motoru Hazır</span>
          </span>
          <h2 className="text-xl sm:text-2xl md:text-3xl font-extrabold tracking-tight">
            Tezlify AI Video Studio
          </h2>
          <p className="text-white/80 text-xs sm:text-sm font-medium leading-relaxed">
            Bilgisayarınızda yerel çalışan, bağımsız ve profesyonel video stüdyosu. Videolarınızı içe aktarın, teknik detaylarını inceleyin ve yayına hazırlayın.
          </p>
          <div className="pt-2 flex flex-wrap gap-2.5">
            <Button
              variant="default"
              size="md"
              onClick={() => onNavigateTab('import-video')}
              className="bg-white text-[#7367F0] hover:bg-white/90 shadow-md gap-2"
            >
              <UploadCloud className="w-4 h-4" />
              <span>Yeni Video İçe Aktar</span>
            </Button>
            <Button
              variant="outline"
              size="md"
              onClick={() => onNavigateTab('media-library')}
              className="border-white/30 bg-white/10 text-white hover:bg-white/20 gap-2"
            >
              <Film className="w-4 h-4" />
              <span>Kütüphaneye Git</span>
            </Button>
          </div>
        </div>
      </div>

      {/* KPI Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Toplam Video"
          value={videos.length}
          subtitle="Kütüphanedeki hazır kayıtlar"
          icon={Film}
          variant="primary"
        />
        <StatsCard
          title="Depolama Alanı"
          value={formatBytes(totalStorage)}
          subtitle={`${systemStatus?.disk_free_gb || 0} GB boş disk alanı`}
          icon={HardDrive}
          variant="info"
        />
        <StatsCard
          title="Toplam Video Süresi"
          value={formatDuration(totalDuration)}
          subtitle="İşlenen medya süresi"
          icon={Clock}
          variant="warning"
        />
        <StatsCard
          title="Sistem Sağlığı"
          value={systemStatus?.status === 'healthy' ? 'Stabil' : 'Kontrol'}
          subtitle={`Python ${systemStatus?.python_version || '3.x'}`}
          icon={Activity}
          variant="success"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Videos List (2 Cols) */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle>Son Eklenen Videolar</CardTitle>
                <p className="text-xs text-slate-500 dark:text-[#7E7F96]">
                  En son sisteme aktarılan medya dosyaları
                </p>
              </div>
              {videos.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onNavigateTab('media-library')}
                  className="gap-1 text-[#7367F0]"
                >
                  <span>Tümünü Gör</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Button>
              )}
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="p-8 text-center text-xs text-slate-400">Yükleniyor...</div>
              ) : videos.length === 0 ? (
                <div className="text-center py-10 space-y-3">
                  <div className="w-12 h-12 rounded-2xl bg-[#7367F0]/10 text-[#7367F0] flex items-center justify-center mx-auto">
                    <Film className="w-6 h-6" />
                  </div>
                  <p className="text-xs font-semibold text-slate-600 dark:text-slate-300">
                    Henüz hiç video yüklenmedi
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onNavigateTab('import-video')}
                  >
                    İlk Videoyu Aktar
                  </Button>
                </div>
              ) : (
                <div className="divide-y divide-slate-100 dark:divide-white/[0.05]">
                  {videos.slice(0, 5).map((asset) => (
                    <div
                      key={asset.id}
                      onClick={() => onSelectVideo(asset)}
                      className="py-3 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-white/[0.02] -mx-5 px-5 cursor-pointer transition-colors"
                    >
                      <div className="flex items-center space-x-3 truncate">
                        <div className="w-10 h-10 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-600 dark:text-slate-300 shrink-0">
                          <Play className="w-4 h-4 text-[#7367F0]" />
                        </div>
                        <div className="truncate">
                          <h4 className="text-xs font-bold text-slate-800 dark:text-white truncate">
                            {asset.original_filename}
                          </h4>
                          <div className="flex items-center space-x-2 text-[11px] text-slate-400 dark:text-[#7E7F96]">
                            <span>{formatBytes(asset.file_size_bytes)}</span>
                            <span>•</span>
                            <span>{formatDuration(asset.metadata?.duration_seconds)}</span>
                            {asset.metadata?.resolution_label && (
                              <>
                                <span>•</span>
                                <span>{asset.metadata.resolution_label}</span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center space-x-3 shrink-0">
                        <StatusBadge status={asset.status} />
                        <span className="text-[11px] text-slate-400 dark:text-[#7E7F96] hidden sm:inline">
                          {formatDate(asset.created_at)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* System & Engine Status Card (1 Col) */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Üretim Motorları Durumu</CardTitle>
              <p className="text-xs text-slate-500 dark:text-[#7E7F96]">
                Yerel işleme ve medya araçları
              </p>
            </CardHeader>
            <CardContent className="space-y-3.5">
              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05]">
                <div className="flex items-center space-x-2.5">
                  <Server className="w-4 h-4 text-[#7367F0]" />
                  <div>
                    <h5 className="text-xs font-bold text-slate-800 dark:text-white">
                      FastAPI Backend
                    </h5>
                    <p className="text-[10px] text-slate-400 dark:text-[#7E7F96]">
                      Port 8000 · SQLite WAL
                    </p>
                  </div>
                </div>
                <span className="inline-flex items-center space-x-1 text-[11px] font-bold text-[#28C76F]">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Aktif</span>
                </span>
              </div>

              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05]">
                <div className="flex items-center space-x-2.5">
                  <Film className="w-4 h-4 text-[#00CFE8]" />
                  <div>
                    <h5 className="text-xs font-bold text-slate-800 dark:text-white">
                      FFmpeg / FFprobe
                    </h5>
                    <p className="text-[10px] text-slate-400 dark:text-[#7E7F96]">
                      Video analizi ve montaj
                    </p>
                  </div>
                </div>
                {systemStatus?.ffmpeg_installed ? (
                  <span className="inline-flex items-center space-x-1 text-[11px] font-bold text-[#28C76F]">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Yüklü</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center space-x-1 text-[11px] font-bold text-[#FF9F43]">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>Python Fallback</span>
                  </span>
                )}
              </div>

              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05]">
                <div className="flex items-center space-x-2.5">
                  <Activity className="w-4 h-4 text-[#FF9F43]" />
                  <div>
                    <h5 className="text-xs font-bold text-slate-800 dark:text-white">
                      Blender 2.5D Motoru
                    </h5>
                    <p className="text-[10px] text-slate-400 dark:text-[#7E7F96]">
                      Aşama 6-8'de entegre edilecek
                    </p>
                  </div>
                </div>
                {systemStatus?.blender_installed ? (
                  <span className="inline-flex items-center space-x-1 text-[11px] font-bold text-[#28C76F]">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Algılandı</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center space-x-1 text-[11px] font-bold text-slate-400">
                    <span>Beklemede</span>
                  </span>
                )}
              </div>

              <div className="pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onNavigateTab('settings')}
                  className="w-full text-xs"
                >
                  Detaylı Sistem Tanısını Aç
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

