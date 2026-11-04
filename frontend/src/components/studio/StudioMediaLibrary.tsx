import React, { useEffect, useMemo, useState } from 'react';
import {
  Captions,
  CheckCircle2,
  Clock3,
  Download,
  Film,
  FolderOpen,
  Loader2,
  Monitor,
  Play,
  RefreshCw,
} from 'lucide-react';
import { RenderJob, StudioProject } from '../../types/studio';
import { apiService } from '../../services/api';
import { formatBytes, formatDate, formatDuration } from '../../lib/utils';
import { renderFormatLabel } from '../../lib/studioWorkspace';
import { Button } from '../ui/button';
import { StudioAlert } from './StudioShared';

interface StudioMediaLibraryProps {
  renders: RenderJob[];
  projects: StudioProject[];
  searchQuery: string;
  onOpenProject: (projectId: string) => void;
}

export const StudioMediaLibrary: React.FC<StudioMediaLibraryProps> = ({
  renders,
  projects,
  searchQuery,
  onOpenProject,
}) => {
  const sortedRenders = useMemo(
    () =>
      [...renders].sort(
        (a, b) =>
          new Date(b.completed_at || b.created_at).getTime() -
          new Date(a.completed_at || a.created_at).getTime()
      ),
    [renders]
  );
  const [selectedId, setSelectedId] = useState<string | null>(
    sortedRenders.find((job) => job.status === 'completed')?.id || sortedRenders[0]?.id || null
  );

  useEffect(() => {
    if (selectedId && sortedRenders.some((job) => job.id === selectedId)) return;
    setSelectedId(
      sortedRenders.find((job) => job.status === 'completed')?.id || sortedRenders[0]?.id || null
    );
  }, [selectedId, sortedRenders]);

  const projectTitle = (projectId: string) =>
    projects.find((project) => project.id === projectId)?.title || projectId;

  const filtered = useMemo(() => {
    const query = searchQuery.trim().toLocaleLowerCase('tr-TR');
    if (!query) return sortedRenders;
    return sortedRenders.filter((job) => {
      const metadata = job.output_metadata;
      const haystack = [
        projectTitle(job.project_id),
        job.project_id,
        metadata?.format || '',
        metadata?.width && metadata?.height ? `${metadata.width}x${metadata.height}` : '',
        metadata?.video_codec || '',
        job.status,
      ]
        .join(' ')
        .toLocaleLowerCase('tr-TR');
      return haystack.includes(query);
    });
  }, [projects, searchQuery, sortedRenders]);

  const selected = sortedRenders.find((job) => job.id === selectedId) || null;
  const completedCount = sortedRenders.filter((job) => job.status === 'completed').length;

  if (renders.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-10 text-center dark:border-white/[0.1] dark:bg-[#2F3349]">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#7367F0]/10 text-[#7367F0]">
          <Film className="h-6 w-6" />
        </div>
        <h3 className="mt-4 text-base font-bold text-slate-900 dark:text-white">
          Studio çıktısı henüz yok
        </h3>
        <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          AI Studio’da bir kompozisyon render’ı tamamlandığında MP4 ve SRT çıktıları burada
          proje ilişkisiyle listelenir.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-white/[0.08] dark:bg-[#2F3349]">
          <div className="flex items-center gap-2 text-[10px] font-semibold text-slate-400">
            <Film className="h-3.5 w-3.5 text-[#7367F0]" />
            Toplam çıktı
          </div>
          <div className="mt-1 text-xl font-extrabold text-slate-900 dark:text-white">
            {sortedRenders.length}
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-white/[0.08] dark:bg-[#2F3349]">
          <div className="flex items-center gap-2 text-[10px] font-semibold text-slate-400">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
            Tamamlanan
          </div>
          <div className="mt-1 text-xl font-extrabold text-slate-900 dark:text-white">
            {completedCount}
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-white/[0.08] dark:bg-[#2F3349]">
          <div className="flex items-center gap-2 text-[10px] font-semibold text-slate-400">
            <Clock3 className="h-3.5 w-3.5 text-amber-500" />
            Aktif
          </div>
          <div className="mt-1 text-xl font-extrabold text-slate-900 dark:text-white">
            {sortedRenders.filter((job) => job.status === 'pending' || job.status === 'running').length}
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-white/[0.08] dark:bg-[#2F3349]">
          <div className="flex items-center gap-2 text-[10px] font-semibold text-slate-400">
            <FolderOpen className="h-3.5 w-3.5 text-sky-500" />
            Proje
          </div>
          <div className="mt-1 text-xl font-extrabold text-slate-900 dark:text-white">
            {new Set(sortedRenders.map((job) => job.project_id)).size}
          </div>
        </div>
      </div>

      {selected && (
        <div className="grid grid-cols-1 gap-4 rounded-2xl border border-slate-200 bg-white p-4 dark:border-white/[0.08] dark:bg-[#2F3349] lg:grid-cols-[minmax(0,1.6fr)_minmax(260px,1fr)]">
          <div>
            {selected.status === 'completed' ? (
              <video
                key={selected.id}
                controls
                preload="metadata"
                src={apiService.getRenderVideoUrl(selected.id)}
                className="max-h-80 w-full rounded-xl bg-black"
              />
            ) : (
              <div className="flex min-h-52 items-center justify-center rounded-xl bg-slate-950">
                <div className="text-center">
                  {selected.status === 'pending' || selected.status === 'running' ? (
                    <Loader2 className="mx-auto h-8 w-8 animate-spin text-[#7367F0]" />
                  ) : (
                    <Film className="mx-auto h-8 w-8 text-white/40" />
                  )}
                  <p className="mt-2 text-xs font-semibold text-white/70">
                    {selected.status} · {selected.current_step}
                  </p>
                </div>
              </div>
            )}
          </div>
          <div className="flex flex-col justify-between gap-3">
            <div>
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-bold text-slate-900 dark:text-white">
                  {projectTitle(selected.project_id)}
                </span>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                    selected.status === 'completed'
                      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
                      : selected.status === 'failed'
                      ? 'bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300'
                      : 'bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300'
                  }`}
                >
                  {selected.status}
                </span>
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
                {selected.output_metadata?.composition_name || 'Studio render çıktısı'}
              </p>
              <div className="mt-3 grid grid-cols-2 gap-2 text-[10px]">
                <div className="rounded-lg bg-slate-50 p-2 dark:bg-white/[0.03]">
                  <div className="text-slate-400">Format</div>
                  <div className="font-bold text-slate-700 dark:text-slate-200">
                    {renderFormatLabel(selected)}
                  </div>
                </div>
                <div className="rounded-lg bg-slate-50 p-2 dark:bg-white/[0.03]">
                  <div className="text-slate-400">Süre</div>
                  <div className="font-bold text-slate-700 dark:text-slate-200">
                    {selected.output_metadata?.duration_seconds
                      ? formatDuration(selected.output_metadata.duration_seconds)
                      : '—'}
                  </div>
                </div>
                <div className="rounded-lg bg-slate-50 p-2 dark:bg-white/[0.03]">
                  <div className="text-slate-400">FPS / Codec</div>
                  <div className="font-bold text-slate-700 dark:text-slate-200">
                    {selected.output_metadata?.fps || '—'} /{' '}
                    {selected.output_metadata?.video_codec || '—'}
                  </div>
                </div>
                <div className="rounded-lg bg-slate-50 p-2 dark:bg-white/[0.03]">
                  <div className="text-slate-400">Boyut</div>
                  <div className="font-bold text-slate-700 dark:text-slate-200">
                    {selected.output_metadata?.file_size_bytes
                      ? formatBytes(selected.output_metadata.file_size_bytes)
                      : '—'}
                  </div>
                </div>
              </div>
              {selected.error_message && (
                <details className="mt-2 rounded-lg bg-red-50 p-2 text-[10px] text-red-700 dark:bg-red-950/30 dark:text-red-300">
                  <summary className="cursor-pointer font-bold">Teknik hata</summary>
                  <p className="mt-1 whitespace-pre-wrap break-words">{selected.error_message}</p>
                </details>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {selected.status === 'completed' && (
                <a
                  href={apiService.getRenderVideoUrl(selected.id)}
                  download
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[#7367F0] px-3 py-1.5 text-[11px] font-bold text-white transition hover:bg-[#685DD8]"
                >
                  <Download className="h-3.5 w-3.5" />
                  MP4 indir
                </a>
              )}
              {selected.output_metadata?.subtitle_file_path && (
                <a
                  href={apiService.getRenderSubtitlesUrl(selected.id)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-[11px] font-bold text-slate-700 transition hover:border-[#7367F0] hover:text-[#7367F0] dark:border-white/[0.12] dark:text-slate-200"
                >
                  <Captions className="h-3.5 w-3.5" />
                  SRT indir
                </a>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => onOpenProject(selected.project_id)}
                className="gap-1.5"
              >
                <FolderOpen className="h-3.5 w-3.5" />
                Projeye dön
              </Button>
            </div>
          </div>
        </div>
      )}

      {filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-xs text-slate-400 dark:border-white/[0.1]">
          Arama kriterine uyan Studio çıktısı bulunamadı.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((job) => (
            <button
              key={job.id}
              type="button"
              onClick={() => setSelectedId(job.id)}
              className={`overflow-hidden rounded-xl border bg-white text-left transition hover:-translate-y-0.5 hover:shadow-md dark:bg-[#2F3349] ${
                selectedId === job.id
                  ? 'border-[#7367F0]'
                  : 'border-slate-200 dark:border-white/[0.08]'
              }`}
            >
              <div className="flex h-28 items-center justify-center bg-slate-950">
                <div className="text-center">
                  {job.status === 'completed' ? (
                    <Play className="mx-auto h-7 w-7 text-white/70" />
                  ) : job.status === 'pending' || job.status === 'running' ? (
                    <RefreshCw className="mx-auto h-7 w-7 animate-spin text-[#7367F0]" />
                  ) : (
                    <Film className="mx-auto h-7 w-7 text-white/40" />
                  )}
                  <div className="mt-1 text-[10px] font-bold text-white/60">
                    {renderFormatLabel(job)}
                  </div>
                </div>
              </div>
              <div className="p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-xs font-bold text-slate-800 dark:text-white">
                    {projectTitle(job.project_id)}
                  </span>
                  <span className="shrink-0 text-[9px] text-slate-400">
                    {job.output_metadata?.duration_seconds
                      ? formatDuration(job.output_metadata.duration_seconds)
                      : '—'}
                  </span>
                </div>
                <div className="mt-1 flex items-center justify-between gap-2 text-[10px] text-slate-400">
                  <span className="truncate font-mono">{job.project_id}</span>
                  <span>{formatDate(job.completed_at || job.created_at)}</span>
                </div>
                <div className="mt-2 flex items-center gap-1 text-[9px] text-slate-400">
                  <Monitor className="h-3 w-3" />
                  {job.output_metadata?.width && job.output_metadata?.height
                    ? `${job.output_metadata.width} × ${job.output_metadata.height}`
                    : 'Çözünürlük bilgisi yok'}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {selected?.status === 'failed' && (
        <StudioAlert tone="error">
          Seçili render başarısız. AI Studio üretim akışındaki Animasyon veya Kompozisyon adımından
          yeni bir render başlatabilirsiniz.
        </StudioAlert>
      )}
    </div>
  );
};
