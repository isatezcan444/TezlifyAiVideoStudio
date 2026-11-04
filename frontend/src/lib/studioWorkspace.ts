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
      case 'export':
        completed = hasComposition;
        if (!hasComposition) missing.push('Tamamlanmış bir kompozisyon render’ı yok.');
        break;
      default:
        break;
    }

    return { id: step.id, completed, missing };
  });
}

export function nextWorkflowStep(states: WorkflowStepState[]): WorkflowStepId {
  return states.find((state) => !state.completed)?.id || 'export';
}
