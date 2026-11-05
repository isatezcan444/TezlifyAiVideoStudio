import {
  CompositionSummary,
  RenderJob,
  SceneGraph,
  StudioProject,
} from '../types/studio';

export type StudioView = 'dashboard' | 'projects' | 'workflow';

export type WorkflowStepId =
  | 'project'
  | 'story'
  | 'characters'
  | 'scenes'
  | 'animation'
  | 'composition'
  | 'export';

export interface WorkflowStepDefinition {
  id: WorkflowStepId;
  label: string;
  description: string;
}

export const WORKFLOW_STEPS: WorkflowStepDefinition[] = [
  { id: 'project', label: 'Proje', description: 'Ad, açıklama ve temel bilgiler' },
  { id: 'story', label: 'Hikâye', description: 'Senaryo ve sahne iskeleti' },
  { id: 'characters', label: 'Karakterler', description: 'Kadro, görünüm ve ses profili' },
  { id: 'scenes', label: 'Sahneler', description: 'Sıra, süre ve diyaloglar' },
  { id: 'animation', label: 'Animasyon', description: 'Blender render ve ses sentezi' },
  { id: 'composition', label: 'Kompozisyon', description: 'Geçişler, metinler ve altyazılar' },
  { id: 'export', label: 'Dışa Aktar', description: 'MP4, SRT ve çıktı geçmişi' },
];

export interface WorkflowStepState {
  id: WorkflowStepId;
  completed: boolean;
  missing: string[];
}

export function isActiveRender(job: RenderJob | null | undefined): boolean {
  return Boolean(job && (job.status === 'pending' || job.status === 'running'));
}

/**
 * A `pending` job that was never dispatched.
 *
 * Dispatch is an in-process thread, so every job left `pending` by a previous
 * server run stays pending forever. The UI used to read that as "render in
 * progress" and permanently disabled the render button. Deriving this at read
 * time - rather than rewriting the rows - keeps the user's stored history
 * untouched while unsticking the interface.
 */
export function isStalePending(job: RenderJob | null | undefined, now = Date.now()): boolean {
  if (!job || job.status !== 'pending' || job.started_at) return false;
  const created = new Date(job.created_at).getTime();
  if (Number.isNaN(created)) return false;
  return now - created > 30 * 60 * 1000;
}

/** True only when the job is both finished and actually waiting on the renderer. */
export function isLiveRender(job: RenderJob | null | undefined, now = Date.now()): boolean {
  if (!job) return false;
  if (job.status === 'running') return true;
  return job.status === 'pending' && !isStalePending(job, now);
}

/**
 * Any finished job whose file can be handed to a player.
 *
 * The export screen used to accept only composition renders, so a completed
 * Blender animation - a real MP4 on disk - showed "Dışa aktarılacak video yok".
 */
export function isPlayableRender(job: RenderJob): boolean {
  return job.status === 'completed' && Boolean(job.output_metadata?.video_file_path);
}

export function isCompositionRender(job: RenderJob): boolean {
  return (
    job.id.startsWith('comp_') ||
    job.output_metadata?.engine === 'FFMPEG_COMPOSITION' ||
    Boolean(job.output_metadata?.composition_id)
  );
}

export function isAnimationRender(job: RenderJob): boolean {
  return !isCompositionRender(job);
}

export function latestRenderForProject(
  jobs: RenderJob[],
  projectId: string,
  kind?: 'animation' | 'composition'
): RenderJob | null {
  return (
    jobs
      .filter((job) => job.project_id === projectId)
      .filter((job) => {
        if (kind === 'composition') return isCompositionRender(job);
        if (kind === 'animation') return isAnimationRender(job);
        return true;
      })
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0] || null
  );
}

export function sceneGraphOf(project: StudioProject | null | undefined): SceneGraph | null {
  if (!project?.scene_graph) return null;
  const sceneGraph = project.scene_graph;
  if (!Array.isArray(sceneGraph.scenes) || !Array.isArray(sceneGraph.characters)) return null;
  return sceneGraph;
}

export function sceneDuration(sceneGraph: SceneGraph | null): number {
  return sceneGraph?.scenes.reduce((total, scene) => total + scene.duration_seconds, 0) || 0;
}

export function renderKindLabel(job: RenderJob): string {
  return isCompositionRender(job) ? 'Kompozisyon' : 'Animasyon';
}

export function renderFormatLabel(job: RenderJob): string {
  const metadata = job.output_metadata;
  if (!metadata) return '—';
  if (metadata.format) return metadata.format;
  if (metadata.width && metadata.height) return `${metadata.width} × ${metadata.height}`;
  return '—';
}

export function projectStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: 'Taslak',
    scenario_ready: 'Senaryo hazır',
    render_queued: 'Render kuyruğunda',
    rendering: 'Render ediliyor',
    completed: 'Tamamlandı',
    failed: 'Başarısız',
    archived: 'Arşivlendi',
  };
  return labels[status] || status;
}

export function workflowState(
  project: StudioProject | null,
  jobs: RenderJob[],
  composition: CompositionSummary | null
): WorkflowStepState[] {
  const sceneGraph = sceneGraphOf(project);
  const projectJobs = project ? jobs.filter((job) => job.project_id === project.id) : [];
  const hasAnimation = projectJobs.some(
    (job) => isAnimationRender(job) && job.status === 'completed'
  );
  const hasComposition = projectJobs.some(
    (job) => isCompositionRender(job) && job.status === 'completed'
  );
  const hasScenes = Boolean(sceneGraph?.scenes.length);
  const hasCharacters = Boolean(sceneGraph?.characters.length);
  const hasDialogue = Boolean(sceneGraph?.scenes.some((scene) => scene.dialogues.length > 0));

  return WORKFLOW_STEPS.map((step) => {
    const missing: string[] = [];
    let completed = false;

    switch (step.id) {
      case 'project':
        completed = Boolean(project?.title.trim());
        if (!project) missing.push('Bir proje seçin veya oluşturun.');
        else if (!project.title.trim()) missing.push('Proje adı zorunludur.');
        break;
      case 'story':
        completed = hasScenes && hasDialogue;
        if (!hasScenes) missing.push('Hikâye üretin veya mevcut sahneleri kullanın.');
        else if (!hasDialogue) missing.push('En az bir sahne diyaloğu ekleyin.');
        break;
      case 'characters':
        completed = hasCharacters;
        if (!hasCharacters) missing.push('Projeye en az bir karakter ekleyin.');
        break;
      case 'scenes':
        completed = hasScenes && sceneGraph!.scenes.every((scene) => scene.duration_seconds > 0);
        if (!hasScenes) missing.push('Düzenlenecek sahne bulunmuyor.');
        break;
      case 'animation':
        completed = hasAnimation;
        if (!hasAnimation) missing.push('İsteğe bağlı: Blender animasyon render’ı tamamlanmadı.');
        break;
      case 'composition':
        completed = Boolean(composition?.is_saved);
        if (!composition?.is_saved) missing.push('Kompozisyon ayarlarını kaydedin.');
        break;
      case 'export': {
        // A finished Blender animation is an MP4 the export screen can play and
        // download, so it satisfies this step just like a composition render.
        const hasPlayable = projectJobs.some((job) => isPlayableRender(job));
        completed = hasComposition || hasPlayable;
        if (!completed) missing.push('Oynatılabilir tamamlanmış bir render yok.');
        break;
      }
      default:
        break;
    }

    return { id: step.id, completed, missing };
  });
}

export function nextWorkflowStep(states: WorkflowStepState[]): WorkflowStepId {
  return states.find((state) => !state.completed)?.id || 'export';
}
