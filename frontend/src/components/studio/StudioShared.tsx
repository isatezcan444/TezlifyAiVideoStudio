import React from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Film,
  Loader2,
  Play,
  XCircle,
} from 'lucide-react';
import { RenderJob, StudioProject } from '../../types/studio';
import { sceneGraphOf } from '../../lib/studioWorkspace';
import { Progress } from '../ui/Progress';
import { cn } from '../../lib/utils';

interface StudioAlertProps {
  tone: 'error' | 'success' | 'info' | 'warning';
  title?: string;
  children: React.ReactNode;
}

const alertTones = {
  error: {
    wrapper:
      'border-red-200 bg-red-50 text-red-700 dark:border-red-900/70 dark:bg-red-950/40 dark:text-red-300',
    icon: AlertCircle,
  },
  success: {
    wrapper:
      'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300',
    icon: CheckCircle2,
  },
  info: {
    wrapper:
      'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300',
    icon: Film,
  },
  warning: {
    wrapper:
      'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300',
    icon: AlertCircle,
  },
};

export const StudioAlert: React.FC<StudioAlertProps> = ({ tone, title, children }) => {
  const { wrapper, icon: Icon } = alertTones[tone];
  return (
    <div className={cn('flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm', wrapper)}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0">
        {title && <div className="font-bold">{title}</div>}
        <div className={cn(title && 'mt-0.5', 'break-words')}>{children}</div>
      </div>
    </div>
  );
};

interface ProjectScenePreviewProps {
  project: StudioProject;
  compact?: boolean;
}

export const ProjectScenePreview: React.FC<ProjectScenePreviewProps> = ({ project, compact }) => {
  const sceneGraph = sceneGraphOf(project);
  const scenes = sceneGraph?.scenes || [];
  const characters = sceneGraph?.characters || [];
  const previewScenes = scenes.slice(0, compact ? 3 : 4);

  if (previewScenes.length === 0) {
    return (
      <div className="flex min-h-24 items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/70 px-3 text-center text-[11px] text-slate-400 dark:border-white/[0.1] dark:bg-white/[0.02]">
        Sahne verisi yok
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-1.5 overflow-hidden rounded-xl bg-slate-950 p-1.5">
        {previewScenes.map((scene, index) => {
          const speaker =
            characters.find((character) => character.id === scene.dialogues[0]?.character_id)?.name ||
            scene.dialogues[0]?.character_id;
          return (
            <div
              key={scene.scene_id}
              className="relative flex min-w-0 flex-1 items-end overflow-hidden rounded-lg px-2 py-2"
              style={{
                background:
                  index % 2 === 0
                    ? 'linear-gradient(145deg, #423a74 0%, #2e294c 100%)'
                    : 'linear-gradient(145deg, #243f4a 0%, #1f2b35 100%)',
              }}
              title={`${scene.scene_id}${speaker ? ` · ${speaker}` : ''}`}
            >
              <div className="absolute right-1 top-1 rounded bg-black/25 px-1 text-[9px] font-bold text-white/70">
                {index + 1}
              </div>
              <div className="min-w-0">
                <div className="truncate text-[10px] font-bold text-white/90">
                  {scene.scene_id}
                </div>
                <div className="truncate text-[9px] text-white/55">
                  {scene.dialogues[0]?.text || scene.camera.angle.replace(/_/g, ' ')}
                </div>
              </div>
            </div>
          );
        })}
        {scenes.length > previewScenes.length && (
          <div className="flex w-8 shrink-0 items-center justify-center rounded-lg bg-white/5 text-[10px] font-bold text-white/55">
            +{scenes.length - previewScenes.length}
          </div>
        )}
      </div>
      {!compact && (
        <div className="flex items-center justify-between gap-2 text-[10px] text-slate-400">
          <span>{scenes.length} sahne</span>
          <span>{characters.length} karakter</span>
          <span>{Math.round(project.total_duration_seconds)} sn</span>
        </div>
      )}
    </div>
  );
};

interface RenderStatusPanelProps {
  job: RenderJob | null;
  onRetry?: () => void;
  retryLabel?: string;
  isRetrying?: boolean;
  showPreview?: boolean;
  videoUrl?: string;
}

const statusMap: Record<
  RenderJob['status'],
  { label: string; tone: string; icon: React.ComponentType<{ className?: string }> }
> = {
  pending: { label: 'Bekliyor', tone: 'text-amber-600 dark:text-amber-400', icon: Clock3 },
  running: { label: 'Çalışıyor', tone: 'text-sky-600 dark:text-sky-400', icon: Loader2 },
  completed: { label: 'Tamamlandı', tone: 'text-emerald-600 dark:text-emerald-400', icon: CheckCircle2 },
  failed: { label: 'Başarısız', tone: 'text-red-600 dark:text-red-400', icon: XCircle },
  cancelled: { label: 'İptal edildi', tone: 'text-slate-500 dark:text-slate-400', icon: XCircle },
};

export const RenderStatusPanel: React.FC<RenderStatusPanelProps> = ({
  job,
  onRetry,
  retryLabel = 'Yeniden dene',
  isRetrying,
  showPreview = false,
  videoUrl,
}) => {
  if (!job) {
    return (
      <div className="rounded-xl border border-dashed border-slate-200 px-4 py-5 text-center text-xs text-slate-500 dark:border-white/[0.1] dark:text-slate-400">
        Henüz render kaydı yok.
      </div>
    );
  }

  const status = statusMap[job.status];
  const StatusIcon = status.icon;

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 p-4 dark:border-white/[0.1]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className={cn('flex items-center gap-1.5 text-xs font-bold', status.tone)}>
          <StatusIcon className={cn('h-4 w-4', job.status === 'running' && 'animate-spin')} />
          {status.label}
        </div>
        <span className="font-mono text-[10px] text-slate-400">{job.id}</span>
      </div>
      <Progress value={job.progress_percent} />
      <div className="flex items-center justify-between gap-3 text-[11px] text-slate-500 dark:text-slate-400">
        <span className="truncate">{job.current_step || status.label}</span>
        <span className="shrink-0 font-semibold">{Math.round(job.progress_percent)}%</span>
      </div>
      {job.error_message && (
        <details className="rounded-lg bg-red-50/80 p-2.5 text-[11px] text-red-700 dark:bg-red-950/30 dark:text-red-300">
          <summary className="cursor-pointer font-bold">Teknik hata ayrıntısı</summary>
          <p className="mt-1.5 whitespace-pre-wrap break-words">{job.error_message}</p>
        </details>
      )}
      {showPreview && job.status === 'completed' && videoUrl && (
        <video
          controls
          preload="metadata"
          src={videoUrl}
          className="max-h-64 w-full rounded-lg bg-black"
        />
      )}
      {job.status === 'failed' && onRetry && (
        <button
          type="button"
          onClick={onRetry}
          disabled={isRetrying}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-[11px] font-bold text-slate-700 transition hover:border-[#7367F0] hover:text-[#7367F0] disabled:opacity-50 dark:border-white/[0.12] dark:text-slate-200"
        >
          {isRetrying ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
          {retryLabel}
        </button>
      )}
    </div>
  );
};

export const StudioSectionTitle: React.FC<{
  title: string;
  description?: string;
  action?: React.ReactNode;
}> = ({ title, description, action }) => (
  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
    <div className="min-w-0">
      <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">{title}</h2>
      {description && (
        <p className="mt-1 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          {description}
        </p>
      )}
    </div>
    {action && <div className="shrink-0">{action}</div>}
  </div>
);

export function formatRenderDuration(job: RenderJob | null): string {
  const seconds = job?.output_metadata?.duration_seconds;
  if (seconds === undefined || seconds === null) return '—';
  return `${seconds.toFixed(1)} sn`;
}
