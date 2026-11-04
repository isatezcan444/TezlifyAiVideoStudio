import React from 'react';
import {
  ArrowRight,
  CheckCircle2,
  Clapperboard,
  Clock3,
  Film,
  FolderKanban,
  Loader2,
  Plus,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import { RenderJob, StudioProject } from '../../types/studio';
import { formatDate } from '../../lib/utils';
import { isActiveRender } from '../../lib/studioWorkspace';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { EmptyState } from '../ui/EmptyState';
import { ProjectScenePreview, formatRenderDuration } from './StudioShared';

interface StudioDashboardProps {
  projects: StudioProject[];
  renders: RenderJob[];
  totalProjects: number;
  isLoading: boolean;
  onNewProject: () => void;
  onOpenProject: (projectId: string) => void;
  onViewProjects: () => void;
}

const statCards = [
  {
    key: 'projects',
    label: 'Toplam proje',
    icon: FolderKanban,
    tone: 'bg-[#7367F0]/10 text-[#7367F0]',
  },
  {
    key: 'active',
    label: 'Devam eden proje',
    icon: TrendingUp,
    tone: 'bg-[#00CFE8]/10 text-[#00CFE8]',
  },
  {
    key: 'completed',
    label: 'Tamamlanan render',
    icon: CheckCircle2,
    tone: 'bg-[#28C76F]/10 text-[#28C76F]',
  },
  {
    key: 'rendering',
    label: 'Aktif render',
    icon: Loader2,
    tone: 'bg-[#FF9F43]/10 text-[#FF9F43]',
  },
] as const;

export const StudioDashboard: React.FC<StudioDashboardProps> = ({
  projects,
  renders,
  totalProjects,
  isLoading,
  onNewProject,
  onOpenProject,
  onViewProjects,
}) => {
  const activeProjects = projects.filter(
    (project) => !['completed', 'archived'].includes(project.status)
  );
  const completedRenders = renders.filter((render) => render.status === 'completed');
  const activeRenders = renders.filter(isActiveRender);
  const recentProjects = [...projects]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 4);
  const recentVideos = [...completedRenders]
    .sort((a, b) => new Date(b.completed_at || b.created_at).getTime() - new Date(a.completed_at || a.created_at).getTime())
    .slice(0, 4);
  const recentRenders = [...renders]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  const stats: Record<(typeof statCards)[number]['key'], string> = {
    projects: String(totalProjects || projects.length),
    active: String(activeProjects.length),
    completed: String(completedRenders.length),
    rendering: String(activeRenders.length),
  };

  const projectName = (projectId: string) =>
    projects.find((project) => project.id === projectId)?.title || projectId;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-[#7367F0]" />
          <p className="mt-3 text-xs font-semibold text-slate-500">Studio verileri yükleniyor...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 rounded-2xl border border-[#7367F0]/15 bg-gradient-to-br from-[#7367F0]/[0.07] via-white to-white p-5 dark:border-[#7367F0]/20 dark:from-[#7367F0]/[0.12] dark:via-[#2F3349] dark:to-[#2F3349] sm:flex-row sm:items-center sm:justify-between sm:p-6">
        <div className="max-w-2xl">
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-[#7367F0]/20 bg-white/80 px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest text-[#7367F0] dark:bg-white/5 dark:text-[#A59DF8]">
            <Sparkles className="h-3 w-3" />
            AI Video Production
          </div>
          <h1 className="text-xl font-extrabold tracking-tight text-slate-900 dark:text-white sm:text-2xl">
            Fikirden yayına, tek bir üretim akışı
          </h1>
          <p className="mt-1.5 text-xs leading-relaxed text-slate-500 dark:text-slate-400 sm:text-sm">
            Hikâyeyi yazın, karakterleri seçin, sahneleri düzenleyin ve kompozisyonu dışa aktarın.
            Tüm adımlar aynı proje bağlamında ilerler.
          </p>
        </div>
        <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
          <Button size="md" onClick={onNewProject} className="gap-2">
            <Plus className="h-4 w-4" />
            Yeni proje
          </Button>
          <Button variant="outline" size="md" onClick={onViewProjects}>
            Projeleri gör
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {statCards.map((card) => {
          const Icon = card.icon;
          return (
            <Card key={card.key}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                      {card.label}
                    </p>
                    <p className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900 dark:text-white">
                      {stats[card.key]}
                    </p>
                  </div>
                  <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${card.tone}`}>
                    <Icon
                      className={`h-4.5 w-4.5 ${
                        card.key === 'rendering' && activeRenders.length > 0 ? 'animate-spin' : ''
                      }`}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader className="flex-row items-center justify-between gap-3 pb-3">
            <div>
              <CardTitle>Son kullanılan projeler</CardTitle>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Kaldığınız yerden devam edin
              </p>
            </div>
            <button
              type="button"
              onClick={onViewProjects}
              className="text-xs font-bold text-[#7367F0] hover:underline"
            >
              Tümü
            </button>
          </CardHeader>
          <CardContent>
            {recentProjects.length === 0 ? (
              <EmptyState
                icon={Clapperboard}
                title="Henüz proje yok"
                description="İlk video projenizi oluşturarak üretim akışına başlayın."
                actionLabel="Yeni proje oluştur"
                onAction={onNewProject}
              />
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {recentProjects.map((project) => (
                  <button
                    key={project.id}
                    type="button"
                    onClick={() => onOpenProject(project.id)}
                    className="group rounded-xl border border-slate-200 bg-white p-3 text-left transition hover:-translate-y-0.5 hover:border-[#7367F0]/40 hover:shadow-md dark:border-white/[0.08] dark:bg-white/[0.02]"
                  >
                    <ProjectScenePreview project={project} compact />
                    <div className="mt-3 flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-bold text-slate-800 group-hover:text-[#7367F0] dark:text-white">
                          {project.title}
                        </p>
                        <p className="mt-0.5 text-[10px] text-slate-400">
                          {project.scene_count} sahne · {Math.round(project.total_duration_seconds)} sn
                        </p>
                      </div>
                      <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-[#7367F0]" />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Render durumu</CardTitle>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Gerçek kuyruk ve tamamlanma kayıtları
            </p>
          </CardHeader>
          <CardContent className="space-y-2">
            {recentRenders.length === 0 ? (
              <p className="rounded-xl border border-dashed border-slate-200 p-4 text-center text-xs text-slate-400 dark:border-white/[0.1]">
                Henüz render kaydı yok.
              </p>
            ) : (
              recentRenders.map((render) => (
                <button
                  key={render.id}
                  type="button"
                  onClick={() => onOpenProject(render.project_id)}
                  className="w-full rounded-lg border border-slate-200 p-2.5 text-left transition hover:border-[#7367F0]/40 dark:border-white/[0.08]"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[11px] font-bold text-slate-700 dark:text-slate-200">
                      {projectName(render.project_id)}
                    </span>
                    <span
                      className={`shrink-0 text-[10px] font-bold ${
                        render.status === 'completed'
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : render.status === 'failed'
                          ? 'text-red-600 dark:text-red-400'
                          : 'text-amber-600 dark:text-amber-400'
                      }`}
                    >
                      {Math.round(render.progress_percent)}%
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-1.5 text-[10px] text-slate-400">
                    {isActiveRender(render) ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <Clock3 className="h-3 w-3" />
                    )}
                    <span className="truncate">{render.current_step || render.status}</span>
                  </div>
                </button>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between gap-3 pb-3">
          <div>
            <CardTitle>Son oluşturulan videolar</CardTitle>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Tamamlanmış render çıktıları
            </p>
          </div>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-500 dark:bg-white/[0.06] dark:text-slate-300">
            {completedRenders.length} video
          </span>
        </CardHeader>
        <CardContent>
          {recentVideos.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-200 p-6 text-center text-xs text-slate-400 dark:border-white/[0.1]">
              Tamamlanmış bir video render’ı henüz yok.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {recentVideos.map((render) => (
                <button
                  key={render.id}
                  type="button"
                  onClick={() => onOpenProject(render.project_id)}
                  className="group overflow-hidden rounded-xl border border-slate-200 bg-white text-left transition hover:-translate-y-0.5 hover:border-[#7367F0]/40 hover:shadow-md dark:border-white/[0.08] dark:bg-white/[0.02]"
                >
                  <div className="flex h-24 items-center justify-center bg-slate-950">
                    <div className="text-center">
                      <Film className="mx-auto h-6 w-6 text-white/70" />
                      <div className="mt-1 text-[10px] font-bold text-white/70">
                        {render.output_metadata?.format || 'MP4'}
                      </div>
                    </div>
                  </div>
                  <div className="p-3">
                    <p className="truncate text-xs font-bold text-slate-800 group-hover:text-[#7367F0] dark:text-white">
                      {projectName(render.project_id)}
                    </p>
                    <div className="mt-1 flex items-center justify-between gap-2 text-[10px] text-slate-400">
                      <span>{formatRenderDuration(render)}</span>
                      <span>{formatDate(render.completed_at || render.created_at)}</span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
