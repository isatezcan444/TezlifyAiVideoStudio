import React, { useCallback, useEffect, useState } from 'react';
import {
  Clapperboard,
  FolderKanban,
  LayoutDashboard,
  Plus,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import {
  Character,
  CompositionSummary,
  RenderJob,
  SceneGraph,
  StudioProject,
  VoiceProfile,
  VoiceStatusResponse,
} from '../types/studio';
import { apiService } from '../services/api';
import { StudioView } from '../lib/studioWorkspace';
import { Button } from '../components/ui/button';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { StudioAlert } from '../components/studio/StudioShared';
import { ProjectFormModal } from '../components/studio/ProjectFormModal';
import { StudioDashboard } from '../components/studio/StudioDashboard';
import { StudioProjects } from '../components/studio/StudioProjects';
import { StudioWorkflow } from '../components/studio/StudioWorkflow';

interface StudioWorkspacePageProps {
  onOpenMediaLibrary: () => void;
  onOpenCharacterStudio: () => void;
}

const PROJECT_STORAGE_KEY = 'tezlify.studio.project';
const VIEW_STORAGE_KEY = 'tezlify.studio.view';

function readStoredView(): StudioView {
  const stored = localStorage.getItem(VIEW_STORAGE_KEY);
  return stored === 'projects' || stored === 'workflow' ? stored : 'dashboard';
}

export const StudioWorkspacePage: React.FC<StudioWorkspacePageProps> = ({
  onOpenMediaLibrary,
  onOpenCharacterStudio,
}) => {
  const [projects, setProjects] = useState<StudioProject[]>([]);
  const [totalProjects, setTotalProjects] = useState(0);
  const [renders, setRenders] = useState<RenderJob[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [voices, setVoices] = useState<VoiceProfile[]>([]);
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatusResponse | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string>(
    () => localStorage.getItem(PROJECT_STORAGE_KEY) || ''
  );
  const [composition, setComposition] = useState<CompositionSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCompositionLoading, setIsCompositionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<StudioView>(readStoredView);
  const [isProjectModalOpen, setIsProjectModalOpen] = useState(false);
  const [projectToEdit, setProjectToEdit] = useState<StudioProject | null>(null);
  const [projectToDelete, setProjectToDelete] = useState<StudioProject | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const selectedProject =
    projects.find((project) => project.id === selectedProjectId) || projects[0] || null;

  const fetchWorkspace = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [projectResponse, renderResponse, characterResponse, voiceResponse, statusResponse] =
        await Promise.all([
          apiService.listProjects(100, 0),
          apiService.listRenderJobs(200, 0).catch(() => ({ items: [] as RenderJob[], total: 0 })),
          apiService.listCharacters(100, 0).catch(() => ({
            items: [] as Character[],
            total: 0,
            limit: 100,
            offset: 0,
          })),
          apiService.listVoices().catch(() => null),
          apiService.getVoiceStatus().catch(() => null),
        ]);

      setProjects(projectResponse.items);
      setTotalProjects(projectResponse.total);
      setRenders(renderResponse.items);
      setCharacters(characterResponse.items);
      setVoices(voiceResponse?.items || []);
      setVoiceStatus(statusResponse);
      setSelectedProjectId((previous) => {
        const stored = previous || localStorage.getItem(PROJECT_STORAGE_KEY) || '';
        if (projectResponse.items.some((project) => project.id === stored)) return stored;
        return projectResponse.items[0]?.id || '';
      });
    } catch (err: any) {
      setError(err.message || 'Studio verileri yüklenemedi.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWorkspace();
  }, [fetchWorkspace]);

  useEffect(() => {
    localStorage.setItem(VIEW_STORAGE_KEY, view);
  }, [view]);

  useEffect(() => {
    if (selectedProject?.id) {
      setSelectedProjectId(selectedProject.id);
      localStorage.setItem(PROJECT_STORAGE_KEY, selectedProject.id);
    } else {
      localStorage.removeItem(PROJECT_STORAGE_KEY);
    }
  }, [selectedProject?.id]);

  useEffect(() => {
    if (!selectedProject?.id) {
      setComposition(null);
      return;
    }
    let active = true;
    setIsCompositionLoading(true);
    apiService
      .getProjectComposition(selectedProject.id)
      .then((summary) => {
        if (active) setComposition(summary);
      })
      .catch(() => {
        if (active) setComposition(null);
      })
      .finally(() => {
        if (active) setIsCompositionLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedProject?.id]);

  const openProject = (projectId: string) => {
    setSelectedProjectId(projectId);
    localStorage.setItem(PROJECT_STORAGE_KEY, projectId);
    setView('workflow');
  };

  const openProjects = () => setView('projects');

  const createProject = async (data: { title: string; description: string }) => {
    const created = await apiService.createProject(data);
    setProjects((previous) => [created, ...previous]);
    setTotalProjects((previous) => previous + 1);
    setSelectedProjectId(created.id);
    localStorage.setItem(PROJECT_STORAGE_KEY, created.id);
    setProjectToEdit(null);
    setView('workflow');
  };

  const updateProjectMetadata = async (data: { title: string; description: string }) => {
    if (!selectedProject) throw new Error('Proje seçilmedi.');
    const updated = await apiService.updateProject(selectedProject.id, data);
    setProjects((previous) =>
      previous.map((project) => (project.id === updated.id ? updated : project))
    );
    return updated;
  };

  const editProjectMetadata = async (data: { title: string; description: string }) => {
    if (!projectToEdit) return;
    const updated = await apiService.updateProject(projectToEdit.id, data);
    setProjects((previous) =>
      previous.map((project) => (project.id === updated.id ? updated : project))
    );
    if (selectedProject?.id === updated.id) {
      // The selected project is derived from the list; no separate copy exists.
    }
  };

  const saveSceneGraph = async (sceneGraph: SceneGraph, status?: string) => {
    if (!selectedProject) throw new Error('Proje seçilmedi.');
    const updated = await apiService.updateProject(selectedProject.id, {
      scene_graph: sceneGraph,
      status,
    });
    setProjects((previous) =>
      previous.map((project) => (project.id === updated.id ? updated : project))
    );
    return updated;
  };

  const createCharacter = async (data: Partial<Character>) => {
    const created = await apiService.createCharacter(data);
    setCharacters((previous) => [created, ...previous]);
    return created;
  };

  const updateCharacter = async (id: string, data: Partial<Character>) => {
    const updated = await apiService.updateCharacter(id, data);
    setCharacters((previous) =>
      previous.map((character) => (character.id === updated.id ? updated : character))
    );
    return updated;
  };

  const confirmDelete = async () => {
    if (!projectToDelete) return;
    setIsDeleting(true);
    setError(null);
    try {
      await apiService.deleteProject(projectToDelete.id);
      setProjects((previous) => previous.filter((project) => project.id !== projectToDelete.id));
      setTotalProjects((previous) => Math.max(0, previous - 1));
      if (selectedProjectId === projectToDelete.id) {
        const remaining = projects.filter((project) => project.id !== projectToDelete.id);
        setSelectedProjectId(remaining[0]?.id || '');
        setComposition(null);
      }
      setProjectToDelete(null);
    } catch (err: any) {
      setError(err.message || 'Proje silinemedi.');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleProjectSaved = async (data: { title: string; description: string }) => {
    if (projectToEdit) {
      await editProjectMetadata(data);
    } else {
      await createProject(data);
    }
  };

  const openNewProject = () => {
    setProjectToEdit(null);
    setIsProjectModalOpen(true);
  };

  const handleRefresh = useCallback(async () => {
    const [renderResponse, projectResponse] = await Promise.all([
      apiService.listRenderJobs(200, 0).catch(() => null),
      apiService.listProjects(100, 0).catch(() => null),
    ]);
    if (renderResponse) setRenders(renderResponse.items);
    if (projectResponse) {
      setProjects(projectResponse.items);
      setTotalProjects(projectResponse.total);
    }
  }, []);

  const navItems: Array<{ id: StudioView; label: string; icon: typeof LayoutDashboard }> = [
    { id: 'dashboard', label: 'Genel Bakış', icon: LayoutDashboard },
    { id: 'projects', label: 'Projeler', icon: FolderKanban },
    { id: 'workflow', label: 'Üretim Akışı', icon: Clapperboard },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-1 dark:border-white/[0.08] dark:bg-[#2F3349]">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = view === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setView(item.id)}
                className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-bold transition ${
                  active
                    ? 'bg-[#7367F0] text-white shadow-sm'
                    : 'text-slate-500 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-white/[0.05]'
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {item.label}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={fetchWorkspace}
            disabled={isLoading}
            aria-label="Studio verilerini yenile"
            className="rounded-lg border border-slate-200 bg-white p-2 text-slate-500 transition hover:text-[#7367F0] disabled:opacity-50 dark:border-white/[0.08] dark:bg-[#2F3349] dark:text-slate-300"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <Button size="sm" onClick={openNewProject} className="gap-1.5">
            <Plus className="h-3.5 w-3.5" />
            Yeni proje
          </Button>
        </div>
      </div>

      {error && (
        <StudioAlert tone="error" title="Studio verisi alınamadı">
          {error}
        </StudioAlert>
      )}

      {!isLoading && !error && projects.length === 0 && view !== 'projects' && (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-10 text-center dark:border-white/[0.1] dark:bg-[#2F3349]">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#7367F0]/10 text-[#7367F0]">
            <Sparkles className="h-6 w-6" />
          </div>
          <h2 className="mt-4 text-base font-bold text-slate-900 dark:text-white">
            AI Video Studio’ya hoş geldiniz
          </h2>
          <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-slate-500 dark:text-slate-400">
            İlk projenizi oluşturun; hikâye, karakterler, sahneler, animasyon ve kompozisyon aynı
            üretim akışında ilerlesin.
          </p>
          <Button onClick={openNewProject} size="md" className="mt-5 gap-2">
            <Plus className="h-4 w-4" />
            İlk projeyi oluştur
          </Button>
        </div>
      )}

      {view === 'dashboard' && projects.length > 0 && (
        <StudioDashboard
          projects={projects}
          renders={renders}
          totalProjects={totalProjects}
          isLoading={isLoading}
          onNewProject={openNewProject}
          onOpenProject={openProject}
          onViewProjects={() => setView('projects')}
        />
      )}

      {view === 'projects' && (
        <StudioProjects
          projects={projects}
          renders={renders}
          total={totalProjects}
          isLoading={isLoading}
          onNewProject={openNewProject}
          onOpenProject={openProject}
          onEditProject={(project) => {
            setProjectToEdit(project);
            setIsProjectModalOpen(true);
          }}
          onDeleteProject={setProjectToDelete}
        />
      )}

      {view === 'workflow' && (
        <StudioWorkflow
          project={selectedProject}
          projects={projects}
          renders={renders}
          characters={characters}
          voices={voices}
          voiceStatus={voiceStatus}
          composition={composition}
          isLoading={isLoading || isCompositionLoading}
          onSelectProject={openProject}
          onUpdateProject={updateProjectMetadata}
          onSaveSceneGraph={saveSceneGraph}
          onCreateCharacter={createCharacter}
          onUpdateCharacter={updateCharacter}
          onOpenProjects={openProjects}
          onOpenCharacterStudio={onOpenCharacterStudio}
          onOpenMediaLibrary={onOpenMediaLibrary}
          onRefresh={handleRefresh}
          onCompositionSummaryChange={setComposition}
        />
      )}

      <ProjectFormModal
        isOpen={isProjectModalOpen}
        project={projectToEdit}
        onClose={() => {
          setIsProjectModalOpen(false);
          setProjectToEdit(null);
        }}
        onSubmit={handleProjectSaved}
      />

      <ConfirmDialog
        isOpen={Boolean(projectToDelete)}
        onClose={() => setProjectToDelete(null)}
        onConfirm={confirmDelete}
        title="Projeyi silmek istediğinize emin misiniz?"
        description={`"${projectToDelete?.title}" projesi ve SceneGraph kaydı kalıcı olarak silinecek. Bu işlem geri alınamaz.`}
        confirmLabel="Evet, projeyi sil"
        cancelLabel="Vazgeç"
        variant="destructive"
        isLoading={isDeleting}
      />
    </div>
  );
};
