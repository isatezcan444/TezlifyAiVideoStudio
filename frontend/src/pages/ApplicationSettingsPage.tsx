import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { SystemStatus } from '../types/media';
import { apiService } from '../services/api';
import {
  Server,
  HardDrive,
  Cpu,
  RefreshCw,
  Terminal,
  Activity,
  Film,
} from 'lucide-react';

interface ApplicationSettingsPageProps {
  systemStatus: SystemStatus | null;
  onRefreshStatus: () => void;
}

export const ApplicationSettingsPage: React.FC<ApplicationSettingsPageProps> = ({
  systemStatus,
  onRefreshStatus,
}) => {
  const [pingResult, setPingResult] = useState<string | null>(null);
  const [isPinging, setIsPinging] = useState(false);

  const handlePing = async () => {
    setIsPinging(true);
    const start = performance.now();
    try {
      const res = await apiService.getHealth();
      const latency = Math.round(performance.now() - start);
      setPingResult(`Bağlantı Başarılı! Sunucu: ${res.app} (Gecikme: ${latency} ms)`);
    } catch {
      setPingResult('Hata: Backend sunucusuna ulaşılamadı.');
    } finally {
      setIsPinging(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* System Overview Card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Sistem ve Çevre Durumu</CardTitle>
            <p className="text-xs text-slate-500 dark:text-[#7E7F96]">
              Yerel YouTube Creator Studio çalışma ortamı ve araç denetimi
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={onRefreshStatus}
            className="gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Yenile</span>
          </Button>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 text-xs">
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05] space-y-1">
              <span className="text-slate-400 dark:text-[#7E7F96] flex items-center space-x-1.5">
                <Cpu className="w-3.5 h-3.5 text-[#7367F0]" />
                <span>İşletim Sistemi</span>
              </span>
              <p className="font-bold text-slate-800 dark:text-white">
                {systemStatus?.os_name || 'macOS (Darwin arm64)'}
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05] space-y-1">
              <span className="text-slate-400 dark:text-[#7E7F96] flex items-center space-x-1.5">
                <Server className="w-3.5 h-3.5 text-[#28C76F]" />
                <span>Python Sürümü</span>
              </span>
              <p className="font-bold text-slate-800 dark:text-white">
                Python {systemStatus?.python_version || '3.14.x'}
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05] space-y-1">
              <span className="text-slate-400 dark:text-[#7E7F96] flex items-center space-x-1.5">
                <HardDrive className="w-3.5 h-3.5 text-[#00CFE8]" />
                <span>Boş Disk Alanı</span>
              </span>
              <p className="font-bold text-slate-800 dark:text-white">
                {systemStatus?.disk_free_gb || 0} GB / {systemStatus?.disk_total_gb || 0} GB
              </p>
            </div>
          </div>

          {/* Tools Inspection */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-200">
              Gerekli Araçlar ve Durumları
            </h4>

            {/* FFmpeg / FFprobe */}
            <div className="p-4 rounded-xl border border-slate-200 dark:border-white/[0.08] bg-slate-50/50 dark:bg-white/[0.01] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div className="flex items-start space-x-3">
                <div className="p-2 rounded-lg bg-[#7367F0]/10 text-[#7367F0] shrink-0 mt-0.5">
                  <Film className="w-5 h-5" />
                </div>
                <div>
                  <h5 className="text-xs font-bold text-slate-800 dark:text-white flex items-center space-x-2">
                    <span>FFmpeg & FFprobe</span>
                    {systemStatus?.ffmpeg_installed ? (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#28C76F]/15 text-[#28C76F] font-bold">
                        Yüklü
                      </span>
                    ) : (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#FF9F43]/15 text-[#FF9F43] font-bold">
                        Python Fallback Aktif
                      </span>
                    )}
                  </h5>
                  <p className="text-[11px] text-slate-500 dark:text-[#7E7F96] mt-0.5">
                    {systemStatus?.ffmpeg_installed
                      ? 'Video codec doğrulama, süre ve thumbnail çıkarma donanım hızlandırmalı çalışıyor.'
                      : 'Sistemde FFprobe bulunamadı. Yerel MP4 başlık ayrıştırıcısı (pure-Python) devrede. Daha hızlı analiz ve thumbnail için Homebrew ile kurabilirsiniz.'}
                  </p>
                  {!systemStatus?.ffmpeg_installed && (
                    <div className="mt-2 flex items-center space-x-2 font-mono text-[11px] bg-slate-200 dark:bg-black/40 px-2.5 py-1 rounded-md text-slate-800 dark:text-slate-200 select-all">
                      <Terminal className="w-3.5 h-3.5" />
                      <span>brew install ffmpeg</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

          </div>

          {/* Storage Paths Information */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05] space-y-2 text-xs">
            <span className="font-bold text-slate-800 dark:text-white block">
              Veri ve Medya Depolama Konumları (Local-First):
            </span>
            <div className="space-y-1 font-mono text-[11px] text-slate-600 dark:text-slate-300">
              <div>
                <span className="text-slate-400">Ana Veri Dizini: </span>
                <span>{systemStatus?.data_dir || './data'}</span>
              </div>
              <div>
                <span className="text-slate-400">SQLite Veritabanı: </span>
                <span>{systemStatus?.data_dir}/database/tezlify_studio.db</span>
              </div>
              <div>
                <span className="text-slate-400">Medya Kütüphanesi: </span>
                <span>{systemStatus?.data_dir}/media/</span>
              </div>
            </div>
          </div>

          {/* Health Ping Test */}
          <div className="pt-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-t border-slate-100 dark:border-white/[0.08]">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePing}
              disabled={isPinging}
              className="gap-2"
            >
              <Activity className="w-3.5 h-3.5 text-[#28C76F]" />
              <span>{isPinging ? 'Ping Yapılıyor...' : 'Backend Bağlantısını Test Et'}</span>
            </Button>
            {pingResult && (
              <span className="text-xs font-semibold text-[#7367F0]">
                {pingResult}
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
