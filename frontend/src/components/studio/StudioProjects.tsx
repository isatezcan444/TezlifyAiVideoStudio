import React, { useMemo, useState } from 'react';
import {
  ArrowRight,
  Clock3,
  Edit2,
  Film,
  Loader2,
  Plus,
  Search,
  Trash2,
} from 'lucide-react';
import { RenderJob, StudioProject } from '../../types/studio';
import { formatDate } from '../../lib/utils';
import {
  isActiveRender,
  isCompositionRender,
  latestRenderForProject,
  renderFormatLabel,
  renderKindLabel,
} from '../../lib/studioWorkspace';
import { Button } from '../ui/button';
import { EmptyState } from '../ui/EmptyState';
import { ProjectScenePreview, formatRenderDuration } from './StudioShared';

interface StudioProjectsProps {
  projects: StudioProject[];
  renders: RenderJob[];
  total: number;
  isLoading: boolean;
  onNewProject: () => void;
  onOpenProject: (projectId: string) => void;
  onEditProject: (project: StudioProject) => void;
  onDeleteProject: (project: StudioProject) => void;
}

type StatusFilter = 'all' | 'active' | 'completed';

export const StudioProjects: React.FC<StudioProjectsProps> = ({
  projects,
  renders,
  total,
  isLoading,
  onNewProject,
  onOpenProject,
  onEditProject,
  onDeleteProject,
}) => {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<StatusFilter>('all');

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('tr-TR');
    return projects
      .filter((project) => {
        if (!normalized) return true;
        return (
          project.title.toLocaleLowerCase('tr-TR').includes(normalized) ||
          project.description.toLocaleLowerCase('tr-TR').includes(normalized)
        );
      })
      .filter((project) => {
        if (filter === 'active') return !['completed', 'archived'].includes(project.status);
        if (filter === 'completed') return project.status === 'completed';
        return true;
      })
      .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
  }, [filter, projects, query]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-[#7367F0]" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-extrabold tracking-tight text-slate-900 dark:text-white">
            Projeler
          </h1>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            {total} proje kaydı · oluşturma, düzenleme ve üretim akışına devam etme
          </p>
        </div>
        <Button size="md" onClick={onNewProject} className="gap-2">
          <Plus className="h-4 w-4" />
          Yeni proje
        </Button>
      </div>

      <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-3 dark:border-white/[0.08] dark:bg-[#2F3349] sm:flex-row sm:items-center sm:justify-between">
        <div className="relative min-w-0 flex-1 sm:max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Proje ara..."
            aria-label="Proje ara"
            className="vuexy-input h-9 w-full pl-9 pr-3 text-xs"
          />
        </div>
        <div className="flex gap-1.5 overflow-x-auto">
          {(
            [
              ['all', 'Tümü'],
              ['active', 'Devam eden'],
              ['completed', 'Tamamlanan'],
            ] as Array<[StatusFilter, string]>
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setFilter(value)}
              className={`shrink-0 rounded-lg px-3 py-1.5 text-[11px] font-bold transition ${
                filter === value
                  ? 'bg-[#7367F0] text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-white/[0.06] dark:text-slate-300 dark:hover:bg-white/[0.1]'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={Film}
          title={query || filter !== 'all' ? 'Eşleşen proje yok' : 'Henüz proje yok'}
          description={
            query || filter !== 'all'
              ? 'Arama veya filtreyi değiştirerek tekrar deneyin.'
              : 'İlk projenizi oluşturun; hikâye, karakter ve sahneleri tek akışta hazırlayın.'
          }
          actionLabel={query || filter !== 'all' ? undefined : 'Yeni proje oluştur'}
          onAction={query || filter !== 'all' ? undefined : onNewProject}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {filtered.map((project) => {
            const latestRender = latestRenderForProject(renders, project.id);
            return (
              <article
                key={project.id}
                className="group flex min-w-0 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white transition hover:border-[#7367F0]/35 hover:shadow-md dark:border-white/[0.08] dark:bg-[#2F3349]"
              >
                <div className="p-4 pb-3">
                  <ProjectScenePreview project={project} />
                </div>
                <div className="flex flex-1 flex-col px-4 pb-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h2 className="truncate text-sm font-bold text-slate-900 dark:text-white">
                        {project.title}
                      </h2>
                      <p className="mt-1 line-clamp-2 min-h-8 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
                        {project.description || 'Açıklama eklenmedi.'}
                      </p>
                    </div>
                    <span
                      className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                        project.status === 'completed'
                          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
                          : project.status === 'failed'
                          ? 'bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300'
                          : 'bg-slate-100 text-slate-600 dark:bg-white/[0.06] dark:text-slate-300'
                      }`}
                    >
                      {project.status === 'completed'
                        ? 'Tamamlandı'
                        : project.status === 'failed'
                        ? 'Başarısız'
                        : project.status === 'scenario_ready'
                        ? 'Senaryo hazır'
                        : project.status === 'rendering'
                        ? 'Render'
                        : 'Taslak'}
                    </span>
                  </div>

                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <div className="rounded-lg bg-slate-50 px-2 py-1.5 dark:bg-white/[0.03]">
                      <div className="text-[9px] font-semibold uppercase tracking-wide text-slate-400">
                        Sahne
                      </div>
                      <div className="text-xs font-bold text-slate-700 dark:text-slate-200">
                        {project.scene_count}
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-50 px-2 py-1.5 dark:bg-white/[0.03]">
                      <div className="text-[9px] font-semibold uppercase tracking-wide text-slate-400">
                        Süre
                      </div>
                      <div className="text-xs font-bold text-slate-700 dark:text-slate-200">
                        {Math.round(project.total_duration_seconds)} sn
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-50 px-2 py-1.5 dark:bg-white/[0.03]">
                      <div className="text-[9px] font-semibold uppercase tracking-wide text-slate-400">
                        Karakter
                      </div>
                      <div className="text-xs font-bold text-slate-700 dark:text-slate-200">
                        {project.character_count}
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center justify-between gap-2 rounded-lg border border-slate-200/80 px-2.5 py-2 dark:border-white/[0.08]">
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 text-[10px] font-bold text-slate-500 dark:text-slate-400">
                        {latestRender && isActiveRender(latestRender) && (
                          <Loader2 className="h-3 w-3 animate-spin text-amber-500" />
                        )}
                        {latestRender ? (
                          <>
                            {renderKindLabel(latestRender)}
                            {isCompositionRender(latestRender) && ` · ${renderFormatLabel(latestRender)}`}
                          </>
                        ) : (
                          <span className="inline-flex items-center gap-1">
                            <Clock3 className="h-3 w-3" />
                            Render yok
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 truncate text-[10px] text-slate-400">
                        {latestRender
                          ? `${latestRender.status} · ${formatRenderDuration(latestRender)}`
                          : `Oluşturuldu ${formatDate(project.created_at)}`}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => onOpenProject(project.id)}
                      className="inline-flex shrink-0 items-center gap-1 text-[11px] font-bold text-[#7367F0] hover:underline"
                    >
                      Düzenle
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  <div className="mt-3 flex items-center justify-between gap-2 border-t border-slate-100 pt-3 dark:border-white/[0.06]">
                    <span className="text-[10px] text-slate-400">
                      {formatDate(project.updated_at)} güncellendi
                    </span>
                    <div className="flex gap-1">
                      <button
                        type="button"
                        onClick={() => onEditProject(project)}
                        aria-label={`${project.title} projesini düzenle`}
                        className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-[#7367F0] dark:hover:bg-white/[0.06]"
                      >
                        <Edit2 className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => onDeleteProject(project)}
                        aria-label={`${project.title} projesini sil`}
                        className="rounded-lg p-1.5 text-slate-400 transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
};
