import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  Captions,
  CheckCircle2,
  Download,
  Film,
  FolderOpen,
  Loader2,
  Monitor,
  Play,
  RefreshCw,
} from 'lucide-react';
import {
  CompositionSummary,
  RenderJob,
  StudioProject,
} from '../../../types/studio';
import { apiService } from '../../../services/api';
import { formatBytes, formatDate, formatDuration } from '../../../lib/utils';
import {
  isActiveRender,
  isCompositionRender,
  renderFormatLabel,
} from '../../../lib/studioWorkspace';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { StudioAlert, StudioSectionTitle } from '../StudioShared';

interface ExportStepProps {
  project: StudioProject;
  renders: RenderJob[];
  composition: CompositionSummary | null;
  onOpenComposition: () => void;
  onOpenProjects: () => void;
  onOpenMediaLibrary: () => void;
  onRefresh: () => Promise<void>;
}

/**
 * Lip-sync status must tell the truth about provenance: real alignment, local
 * alignment, provider alignment, pending, failed, or the legacy mouth animation.
 * A render that fell back may never read as "Gerçek Lip-Sync".
 */
export function lipSyncLabel(metadata?: RenderJob['output_metadata']): string {
  const lipSync = metadata?.lip_sync;
  if (!lipSync) return 'Eski render (lip-sync bilgisi yok)';
  if (lipSync.speakers_aligned > 0) {
    return `Gerçek lip-sync · ${lipSync.speakers_aligned}/${lipSync.speakers_total} konuşmacı`;
  }
  return 'Basit ağız animasyonu (alignment yok)';
}

function metadataRows(job: RenderJob) {
  const metadata = job.output_metadata;
  return [
    {
      label: 'Çözünürlük',
      value: metadata?.width && metadata?.height ? `${metadata.width} × ${metadata.height}` : '—',
    },
    { label: 'Format', value: metadata?.format || renderFormatLabel(job) },
    { label: 'FPS', value: metadata?.fps ? String(metadata.fps) : '—' },
    { label: 'Video codec', value: metadata?.video_codec || '—' },
    { label: 'Süre', value: metadata?.duration_seconds ? formatDuration(metadata.duration_seconds) : '—' },
    { label: 'Dosya boyutu', value: metadata?.file_size_bytes ? formatBytes(metadata.file_size_bytes) : '—' },
    { label: 'Lip-sync', value: lipSyncLabel(metadata) },
  ];
}

export const ExportStep: React.FC<ExportStepProps> = ({
  project,
  renders,
  composition,
  onOpenComposition,
  onOpenProjects,
  onOpenMediaLibrary,
  onRefresh,
}) => {
  const compositionRenders = useMemo(
    () =>
      renders
        .filter((job) => job.project_id === project.id && isCompositionRender(job))
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [project.id, renders]
  );
  const [selectedJobId, setSelectedJobId] = useState<string | null>(
    compositionRenders.find((job) => job.status === 'completed')?.id || compositionRenders[0]?.id || null
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (selectedJobId && compositionRenders.some((job) => job.id === selectedJobId)) return;
    setSelectedJobId(
      compositionRenders.find((job) => job.status === 'completed')?.id || compositionRenders[0]?.id || null
    );
  }, [compositionRenders, selectedJobId]);

  const selectedJob = compositionRenders.find((job) => job.id === selectedJobId) || null;
  const completedJobs = compositionRenders.filter((job) => job.status === 'completed');

  useEffect(() => {
    if (!selectedJob || !isActiveRender(selectedJob)) return;
    let active = true;
    const timer = setInterval(async () => {
      try {
        const updated = await apiService.getRenderJob(selectedJob.id);
        if (!active) return;
        if (updated.status === 'completed' || updated.status === 'failed') {
          await onRefresh();
        }
      } catch {
        // Keep the last known state if a poll fails.
      }
    }, 2000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [selectedJob, onRefresh]);

  const downloadSelected = () => {
    if (!selectedJob) {
      setError('İndirilecek render seçilmedi.');
      return;
    }
    window.open(apiService.getRenderVideoUrl(selectedJob.id), '_blank', 'noopener,noreferrer');
  };

  if (compositionRenders.length === 0) {
    return (
      <div className="space-y-5">
        <StudioSectionTitle
          title="Dışa aktar"
          description="Bu proje için henüz kompozisyon render’ı yok. Kompozisyon adımında formatı seçip render başlatın."
        />
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-10 text-center dark:border-white/[0.1] dark:bg-[#2F3349]">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#7367F0]/10 text-[#7367F0]">
            <Play className="h-6 w-6" />
          </div>
          <h3 className="mt-4 text-base font-bold text-slate-900 dark:text-white">
            Dışa aktarılacak video yok
          </h3>
          <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-slate-500 dark:text-slate-400">
            Sahneleri ve kompozisyon ayarlarını tamamlayın. Render tamamlandığında MP4 ve varsa SRT
            dosyası burada listelenir.
          </p>
          <div className="mt-5 flex flex-col justify-center gap-2 sm:flex-row">
            <Button onClick={onOpenComposition} size="md" className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              Kompozisyona dön
            </Button>
            <Button variant="outline" size="md" onClick={onOpenProjects}>
              <FolderOpen className="h-4 w-4" />
              Projelere dön
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <StudioSectionTitle
        title="Dışa aktar"
        description="Tamamlanan kompozisyon render’larını izleyin, MP4/SRT indirin ve gerçek çıktı bilgilerini inceleyin."
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={onOpenMediaLibrary} className="gap-1.5">
              <Film className="h-3.5 w-3.5" />
              Medya kütüphanesi
            </Button>
            <Button variant="outline" size="sm" onClick={onOpenComposition} className="gap-1.5">
              <RefreshCw className="h-3.5 w-3.5" />
              Yeni render
            </Button>
          </div>
        }
      />

      {error && <StudioAlert tone="error">{error}</StudioAlert>}
      {!composition?.is_saved && (
        <StudioAlert tone="warning">
          Kayıtlı kompozisyon bulunamadı. Mevcut render geçmişi görüntülenebilir; yeni render için
          kompozisyonu kaydedin.
        </StudioAlert>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <Play className="h-4 w-4 text-[#7367F0]" />
              Video önizleme
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {selectedJob?.status === 'completed' ? (
              <video
                key={selectedJob.id}
                controls
                preload="metadata"
                src={apiService.getRenderVideoUrl(selectedJob.id)}
                className="max-h-[420px] w-full rounded-xl bg-black"
              />
            ) : (
              <div className="flex min-h-52 items-center justify-center rounded-xl bg-slate-950">
                <div className="text-center">
                  {selectedJob && isActiveRender(selectedJob) ? (
                    <Loader2 className="mx-auto h-8 w-8 animate-spin text-[#7367F0]" />
                  ) : (
                    <Film className="mx-auto h-8 w-8 text-white/50" />
                  )}
                  <p className="mt-2 text-xs font-semibold text-white/70">
                    {selectedJob
                      ? `${selectedJob.status} · ${selectedJob.current_step}`
                      : 'Render seçilmedi'}
                  </p>
                </div>
              </div>
            )}

            {selectedJob && (
              <>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono text-[10px] text-slate-400">{selectedJob.id}</span>
                  <div className="flex flex-wrap gap-2">
                    {selectedJob.status === 'completed' && (
                      <Button size="sm" onClick={downloadSelected} className="gap-1.5">
                        <Download className="h-3.5 w-3.5" />
                        MP4 indir
                      </Button>
                    )}
                    {selectedJob.output_metadata?.subtitle_file_path && (
                      <a
                        href={apiService.getRenderSubtitlesUrl(selectedJob.id)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-[11px] font-bold text-slate-700 transition hover:border-[#7367F0] hover:text-[#7367F0] dark:border-white/[0.12] dark:text-slate-200"
                      >
                        <Captions className="h-3.5 w-3.5" />
                        SRT indir ({selectedJob.output_metadata.subtitle_cue_count || 0})
                      </a>
                    )}
                  </div>
                </div>
                {selectedJob.error_message && (
                  <details className="rounded-lg bg-red-50 p-3 text-[11px] text-red-700 dark:bg-red-950/30 dark:text-red-300">
                    <summary className="cursor-pointer font-bold">Teknik hata ayrıntısı</summary>
                    <p className="mt-1 whitespace-pre-wrap break-words">{selectedJob.error_message}</p>
                  </details>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2">
                <Monitor className="h-4 w-4 text-[#7367F0]" />
                Çıktı bilgileri
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {selectedJob ? (
                metadataRows(selectedJob).map((row) => (
                  <div key={row.label} className="flex items-center justify-between gap-2 text-[11px]">
                    <span className="text-slate-500 dark:text-slate-400">{row.label}</span>
                    <span className="truncate font-bold text-slate-700 dark:text-slate-200">{row.value}</span>
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-400">Render seçilmedi.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Proje ilişkisi</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-[11px]">
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-500 dark:text-slate-400">Proje</span>
                <span className="truncate font-bold text-slate-700 dark:text-slate-200">{project.title}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-500 dark:text-slate-400">Proje ID</span>
                <span className="truncate font-mono text-[10px] text-slate-500">{project.id}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-500 dark:text-slate-400">Tamamlanan</span>
                <span className="font-bold text-slate-700 dark:text-slate-200">{completedJobs.length}</span>
              </div>
              <Button variant="outline" size="sm" onClick={onOpenProjects} className="mt-2 w-full gap-1.5">
                <ArrowLeft className="h-3.5 w-3.5" />
                Projeye geri dön
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Render geçmişi</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {compositionRenders.map((job) => (
              <button
                key={job.id}
                type="button"
                onClick={() => setSelectedJobId(job.id)}
                className={`rounded-lg border p-3 text-left transition ${
                  selectedJobId === job.id
                    ? 'border-[#7367F0] bg-[#7367F0]/5'
                    : 'border-slate-200 hover:border-[#7367F0]/40 dark:border-white/[0.08]'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-[11px] font-bold text-slate-700 dark:text-slate-200">
                    {job.output_metadata?.composition_name || renderFormatLabel(job)}
                  </span>
                  <span
                    className={`shrink-0 text-[10px] font-bold ${
                      job.status === 'completed'
                        ? 'text-emerald-600 dark:text-emerald-400'
                        : job.status === 'failed'
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-amber-600 dark:text-amber-400'
                    }`}
                  >
                    {job.status}
                  </span>
                </div>
                <div className="mt-1 flex items-center justify-between gap-2 text-[10px] text-slate-400">
                  <span>{renderFormatLabel(job)}</span>
                  <span>{formatDate(job.completed_at || job.created_at)}</span>
                </div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {completedJobs.length > 0 && (
        <StudioAlert tone="success">
          <span className="inline-flex items-center gap-1">
            <CheckCircle2 className="h-3.5 w-3.5" />
            {completedJobs.length} tamamlanmış kompozisyon çıktısı mevcut. MP4 ve SRT dosyaları
            doğrudan backend render endpoint’lerinden indirilir.
          </span>
        </StudioAlert>
      )}
    </div>
  );
};
