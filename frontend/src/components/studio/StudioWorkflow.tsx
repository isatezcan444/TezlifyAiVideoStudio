import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronRight,
  Clapperboard,
  Film,
  FolderOpen,
  Loader2,
  Sparkles,
  Users,
} from 'lucide-react';
import {
  Character,
  CompositionSummary,
  RenderJob,
  SceneGraph,
  StudioProject,
  VoiceProfile,
  VoiceStatusResponse,
} from '../../types/studio';
import {
  nextWorkflowStep,
  workflowState,
  WorkflowStepId,
  WORKFLOW_STEPS,
} from '../../lib/studioWorkspace';
import { Button } from '../ui/button';
import { EmptyState } from '../ui/EmptyState';
import { CompositionStudioPage } from '../../pages/CompositionStudioPage';
import { ProjectStep } from './steps/ProjectStep';
import { StoryStep } from './steps/StoryStep';
import { CharactersStep } from './steps/CharactersStep';
import { ScenesStep } from './steps/ScenesStep';
import { AnimationStep } from './steps/AnimationStep';
import { ExportStep } from './steps/ExportStep';

interface StudioWorkflowProps {
  project: StudioProject | null;
  projects: StudioProject[];
  renders: RenderJob[];
  characters: Character[];
  voices: VoiceProfile[];
  voiceStatus: VoiceStatusResponse | null;
  composition: CompositionSummary | null;
  isLoading: boolean;
  onSelectProject: (projectId: string) => void;
  onUpdateProject: (data: { title: string; description: string }) => Promise<StudioProject>;
  onSaveSceneGraph: (sceneGraph: SceneGraph) => Promise<StudioProject>;
  onCreateCharacter: (data: Partial<Character>) => Promise<Character>;
  onUpdateCharacter: (id: string, data: Partial<Character>) => Promise<Character>;
  onOpenProjects: () => void;
  onOpenCharacterStudio: () => void;
  onOpenMediaLibrary: () => void;
  onRefresh: () => Promise<void>;
  onCompositionSummaryChange: (summary: CompositionSummary | null) => void;
}

const STEP_ICONS: Record<WorkflowStepId, React.ComponentType<{ className?: string }>> = {
  project: FolderOpen,
  story: Sparkles,
  characters: Users,
  scenes: Clapperboard,
  animation: Film,
  composition: Film,
  export: ArrowRight,
};

const STORAGE_KEY = 'tezlify.studio.workflow.step';

export const StudioWorkflow: React.FC<StudioWorkflowProps> = ({
  project,
  projects,
  renders,
  characters,
  voices,
  voiceStatus,
  composition,
  isLoading,
  onSelectProject,
  onUpdateProject,
  onSaveSceneGraph,
  onCreateCharacter,
  onUpdateCharacter,
  onOpenProjects,
  onOpenCharacterStudio,
  onOpenMediaLibrary,
  onRefresh,
  onCompositionSummaryChange,
}) => {
  const [activeStep, setActiveStep] = useState<WorkflowStepId>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return WORKFLOW_STEPS.some((step) => step.id === stored)
      ? (stored as WorkflowStepId)
      : 'project';
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, activeStep);
  }, [activeStep]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-[#7367F0]" />
      </div>
    );
  }

  if (!project) {
    return (
      <EmptyState
        icon={Clapperboard}
        title="Üretim akışı için proje seçin"
        description="Projeler ekranından bir proje açın veya yeni bir proje oluşturun."
        actionLabel="Projelere git"
        onAction={onOpenProjects}
      />
    );
  }

  const states = workflowState(project, renders, composition);
  const completedCount = states.filter((state) => state.completed).length;
  const currentState = states.find((state) => state.id === activeStep);
  const suggestedStep = nextWorkflowStep(states);

  const goToStep = (step: WorkflowStepId) => {
    setActiveStep(step);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const nextStep = () => {
    const index = WORKFLOW_STEPS.findIndex((step) => step.id === activeStep);
    if (index < WORKFLOW_STEPS.length - 1) goToStep(WORKFLOW_STEPS[index + 1].id);
  };

  const previousStep = () => {
    const index = WORKFLOW_STEPS.findIndex((step) => step.id === activeStep);
    if (index > 0) goToStep(WORKFLOW_STEPS[index - 1].id);
  };

  const renderStep = () => {
    switch (activeStep) {
      case 'project':
        return <ProjectStep project={project} onUpdate={onUpdateProject} onNext={nextStep} />;
      case 'story':
        return <StoryStep project={project} onSaveSceneGraph={onSaveSceneGraph} onNext={nextStep} />;
      case 'characters':
        return (
          <CharactersStep
            project={project}
            library={characters}
            voices={voices}
            voiceStatus={voiceStatus}
            onSaveSceneGraph={onSaveSceneGraph}
            onCreateCharacter={onCreateCharacter}
            onUpdateCharacter={onUpdateCharacter}
            onOpenCharacterStudio={onOpenCharacterStudio}
          />
        );
      case 'scenes':
        return (
          <ScenesStep
            project={project}
            renders={renders}
            onSaveSceneGraph={onSaveSceneGraph}
            onNext={nextStep}
          />
        );
      case 'animation':
        return (
          <AnimationStep
            project={project}
            renders={renders}
            voiceStatus={voiceStatus}
            onRefresh={onRefresh}
            onNext={nextStep}
          />
        );
      case 'composition':
        return (
          <CompositionStudioPage
            projectId={project.id}
            embedded
            onSummaryChange={onCompositionSummaryChange}
            onRendered={onRefresh}
          />
        );
      case 'export':
        return (
          <ExportStep
            project={project}
            renders={renders}
            composition={composition}
            onOpenComposition={() => goToStep('composition')}
            onOpenProjects={onOpenProjects}
            onOpenMediaLibrary={onOpenMediaLibrary}
            onRefresh={onRefresh}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-white/[0.08] dark:bg-[#2F3349] sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="truncate text-lg font-extrabold tracking-tight text-slate-900 dark:text-white sm:text-xl">
                {project.title}
              </h1>
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-bold text-slate-600 dark:bg-white/[0.06] dark:text-slate-300">
                {project.scene_count} sahne
              </span>
              <span className="rounded-full bg-[#7367F0]/10 px-2.5 py-0.5 text-[10px] font-bold text-[#7367F0] dark:text-[#A59DF8]">
                %{Math.round((completedCount / WORKFLOW_STEPS.length) * 100)} tamamlandı
              </span>
            </div>
            <p className="mt-1 line-clamp-1 text-xs text-slate-500 dark:text-slate-400">
              {project.description || 'Proje açıklaması eklenmedi.'}
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <select
              value={project.id}
              onChange={(event) => onSelectProject(event.target.value)}
              aria-label="Aktif proje seçimi"
              className="vuexy-input h-9 min-w-0 px-2.5 text-xs font-semibold sm:max-w-xs"
            >
              {projects.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
            <Button variant="outline" size="sm" onClick={onOpenProjects} className="gap-1.5">
              <FolderOpen className="h-3.5 w-3.5" />
              Projeler
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="rounded-2xl border border-slate-200 bg-white p-2 dark:border-white/[0.08] dark:bg-[#2F3349] xl:sticky xl:top-4 xl:self-start">
          <div className="flex gap-1 overflow-x-auto pb-1 xl:flex-col xl:overflow-visible xl:pb-0">
            {WORKFLOW_STEPS.map((step, index) => {
              const state = states.find((item) => item.id === step.id)!;
              const Icon = STEP_ICONS[step.id];
              const isActive = activeStep === step.id;
              return (
                <button
                  key={step.id}
                  type="button"
                  onClick={() => goToStep(step.id)}
                  className={`flex min-w-[130px] flex-1 items-center gap-2 rounded-xl px-2.5 py-2 text-left transition xl:min-w-0 xl:flex-none ${
                    isActive
                      ? 'bg-[#7367F0] text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-white/[0.04]'
                  }`}
                >
                  <span
                    className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
                      isActive
                        ? 'bg-white/20'
                        : state.completed
                        ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-300'
                        : 'bg-slate-100 text-slate-400 dark:bg-white/[0.06]'
                    }`}
                  >
                    {state.completed && !isActive ? (
                      <Check className="h-3.5 w-3.5" />
                    ) : (
                      <Icon className="h-3.5 w-3.5" />
                    )}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-[11px] font-bold">
                      {index + 1}. {step.label}
                    </span>
                    <span
                      className={`block truncate text-[9px] ${
                        isActive ? 'text-white/65' : 'text-slate-400'
                      }`}
                    >
                      {state.completed ? 'Tamamlandı' : step.description}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
          {suggestedStep !== activeStep && (
            <button
              type="button"
              onClick={() => goToStep(suggestedStep)}
              className="mt-2 hidden w-full items-center justify-between gap-2 rounded-xl border border-[#7367F0]/20 bg-[#7367F0]/5 px-2.5 py-2 text-left text-[10px] font-bold text-[#7367F0] transition hover:bg-[#7367F0]/10 dark:text-[#A59DF8] xl:flex"
            >
              <span>Önerilen adım: {WORKFLOW_STEPS.find((step) => step.id === suggestedStep)?.label}</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          )}
        </aside>

        <div className="min-w-0">
          {currentState && !currentState.completed && currentState.missing.length > 0 && (
            <div className="mb-4 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 text-[11px] text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-300">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <div>
                <span className="font-bold">Bu adım için eksikler: </span>
                {currentState.missing.join(' ')}
              </div>
            </div>
          )}

          {renderStep()}

          {activeStep !== 'project' && activeStep !== 'export' && (
            <div className="mt-6 flex flex-col-reverse gap-2 border-t border-slate-200 pt-4 dark:border-white/[0.08] sm:flex-row sm:items-center sm:justify-between">
              <Button variant="outline" size="md" onClick={previousStep} className="gap-1.5">
                <ArrowLeft className="h-4 w-4" />
                Önceki adım
              </Button>
              <Button variant="outline" size="md" onClick={nextStep} className="gap-1.5">
                Sonraki adım
                <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
