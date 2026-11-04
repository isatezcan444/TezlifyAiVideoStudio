import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  Captions,
  CheckCircle2,
  Clapperboard,
  Download,
  Film,
  Layers,
  Loader2,
  Monitor,
  Play,
  Plus,
  RefreshCw,
  Save,
  Smartphone,
  Square,
  Trash2,
  Type,
  Volume2,
} from 'lucide-react';
import {
  CompositionFormat,
  CompositionSummary,
  CompositionTextAnchor,
  CompositionTransition,
  RenderJob,
  StudioProject,
  VideoComposition,
  VoiceStatusResponse,
} from '../types/studio';
import { apiService } from '../services/api';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { EmptyState } from '../components/ui/EmptyState';
import { Progress } from '../components/ui/Progress';
import { Spinner } from '../components/ui/Spinner';
import { StatusBadge } from '../components/ui/StatusBadge';
import {
  buildCompositionTimeline,
  COMPOSITION_FORMAT_DIMENSIONS,
  formatCompositionSeconds,
  TRANSITION_LABELS,
} from '../lib/composition';

const FORMAT_OPTIONS: Array<{
  value: CompositionFormat;
  label: string;
  hint: string;
  icon: typeof Monitor;
}> = [
  { value: '16:9', label: 'Yatay 16:9', hint: '1920 × 1080', icon: Monitor },
  { value: '9:16', label: 'Dikey 9:16', hint: '1080 × 1920', icon: Smartphone },
  { value: '1:1', label: 'Kare 1:1', hint: '1080 × 1080', icon: Square },
];

const ANCHOR_OPTIONS: Array<{ value: CompositionTextAnchor; label: string }> = [
  { value: 'top_left', label: 'Sol Üst' },
  { value: 'top_center', label: 'Üst Orta' },
  { value: 'top_right', label: 'Sağ Üst' },
  { value: 'center_left', label: 'Orta Sol' },
  { value: 'center', label: 'Merkez' },
  { value: 'center_right', label: 'Orta Sağ' },
  { value: 'bottom_left', label: 'Sol Alt' },
  { value: 'bottom_center', label: 'Alt Orta' },
  { value: 'bottom_right', label: 'Sağ Alt' },
];

function cloneComposition(composition: VideoComposition): VideoComposition {
  return JSON.parse(JSON.stringify(composition)) as VideoComposition;
}

function isActiveJob(job: RenderJob | null): boolean {
  return Boolean(job && (job.status === 'pending' || job.status === 'running'));
}

interface CompositionStudioPageProps {
  projectId?: string;
  embedded?: boolean;
  onSummaryChange?: (summary: CompositionSummary | null) => void;
  onRendered?: () => void | Promise<void>;
}

export const CompositionStudioPage: React.FC<CompositionStudioPageProps> = ({
  projectId,
  embedded = false,
  onSummaryChange,
  onRendered,
}) => {
  const [projects, setProjects] = useState<StudioProject[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>(projectId || '');
  const [summary, setSummary] = useState<CompositionSummary | null>(null);
  const [composition, setComposition] = useState<VideoComposition | null>(null);
  const [sceneDurations, setSceneDurations] = useState<Record<string, number>>({});
  const [renders, setRenders] = useState<RenderJob[]>([]);
  const [currentJob, setCurrentJob] = useState<RenderJob | null>(null);
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatusResponse | null>(null);

  const [isLoadingProjects, setIsLoadingProjects] = useState(true);
  const [isLoadingComposition, setIsLoadingComposition] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isStartingRender, setIsStartingRender] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [selectedEngine, setSelectedEngine] = useState<'BLENDER_WORKBENCH' | 'BLENDER_EEVEE'>('BLENDER_WORKBENCH');
  const [synthesizeVoices, setSynthesizeVoices] = useState(true);

  const selectedProject = projects.find((project) => project.id === selectedProjectId) || null;

  const sceneLookup = useMemo(() => {
    const lookup: Record<string, { index: number; dialogue: string | null }> = {};
    const scenes = selectedProject?.scene_graph?.scenes;
    if (Array.isArray(scenes)) {
      scenes.forEach((scene: any, index: number) => {
        const dialogue = Array.isArray(scene.dialogues) && scene.dialogues.length > 0
          ? scene.dialogues[0].text
          : null;
        lookup[scene.scene_id] = { index, dialogue };
      });
    }
    return lookup;
  }, [selectedProject]);

  const localTimeline = useMemo(
    () => (composition ? buildCompositionTimeline(composition, sceneDurations) : null),
    [composition, sceneDurations]
  );

  const fetchProjects = useCallback(async () => {
    setIsLoadingProjects(true);
    setErrorMessage(null);
    try {
      const [projectResponse, voiceResponse] = await Promise.all([
        apiService.listProjects(50, 0),
        apiService.getVoiceStatus().catch(() => null),
      ]);
      setProjects(projectResponse.items);
      setVoiceStatus(voiceResponse);
      setSelectedProjectId(
        (previous) => previous || projectId || projectResponse.items[0]?.id || ''
      );
    } catch (err: any) {
      setErrorMessage(err.message || 'Projeler yüklenemedi.');
    } finally {
      setIsLoadingProjects(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    if (projectId) setSelectedProjectId(projectId);
  }, [projectId]);

  useEffect(() => {
    if (!selectedProjectId) {
      setSummary(null);
      setComposition(null);
      setSceneDurations({});
      setRenders([]);
      setCurrentJob(null);
      onSummaryChange?.(null);
      return;
    }

    let active = true;
    setIsLoadingComposition(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    setIsDirty(false);

    (async () => {
      try {
        const [compositionResponse, renderResponse] = await Promise.all([
          apiService.getProjectComposition(selectedProjectId),
          apiService.listProjectRenders(selectedProjectId).catch(() => ({ items: [], total: 0 })),
        ]);
        if (!active) return;
        setSummary(compositionResponse);
        setComposition(compositionResponse.composition);
        setSceneDurations(
          Object.fromEntries(compositionResponse.timeline.map((entry) => [entry.scene_id, entry.duration_seconds]))
        );
        setRenders(renderResponse.items);
        setCurrentJob(renderResponse.items[0] || null);
        onSummaryChange?.(compositionResponse);
      } catch (err: any) {
        if (!active) return;
        setSummary(null);
        setComposition(null);
        setErrorMessage(err.message || 'Kompozisyon yüklenemedi.');
        onSummaryChange?.(null);
      } finally {
        if (active) setIsLoadingComposition(false);
      }
    })();

    return () => {
      active = false;
    };
  }, [selectedProjectId, onSummaryChange]);

  useEffect(() => {
    if (!isActiveJob(currentJob) || !selectedProjectId) return;
    let active = true;

    const interval = setInterval(async () => {
      try {
        const updated = await apiService.getRenderJob(currentJob!.id);
        if (!active) return;
        setCurrentJob(updated);
        if (updated.status === 'completed' || updated.status === 'failed') {
          const renderResponse = await apiService.listProjectRenders(selectedProjectId).catch(() => null);
          if (active && renderResponse) setRenders(renderResponse.items);
          if (active) await onRendered?.();
        }
      } catch (err: any) {
        if (active) setErrorMessage(err.message || 'Render durumu alınamadı.');
      }
    }, 2000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [currentJob, selectedProjectId, onRendered]);

  const mutateComposition = (mutator: (draft: VideoComposition) => void) => {
    setComposition((previous) => {
      if (!previous) return previous;
      const draft = cloneComposition(previous);
      mutator(draft);
      return draft;
    });
    setIsDirty(true);
    setSuccessMessage(null);
    setErrorMessage(null);
  };

  const handleFormatChange = (format: CompositionFormat) => {
    mutateComposition((draft) => {
      draft.format = format;
      const dimensions = COMPOSITION_FORMAT_DIMENSIONS[format];
      draft.width = dimensions.width;
      draft.height = dimensions.height;
    });
  };

  const moveScene = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (!composition || target < 0 || target >= composition.scenes.length) return;
    mutateComposition((draft) => {
      const [moved] = draft.scenes.splice(index, 1);
      draft.scenes.splice(target, 0, moved);
    });
  };

  const updateSceneTransition = (index: number, transition: CompositionTransition) => {
    mutateComposition((draft) => {
      const scene = draft.scenes[index];
      scene.transition = transition;
      scene.transition_duration_seconds =
        transition === 'cut' ? 0 : scene.transition_duration_seconds > 0 ? scene.transition_duration_seconds : 0.5;
    });
  };

  const updateSceneTransitionDuration = (index: number, duration: number) => {
    mutateComposition((draft) => {
      draft.scenes[index].transition_duration_seconds = Math.max(0, Number.isFinite(duration) ? duration : 0);
    });
  };

  const addTextLayer = (kind: 'title' | 'closing') => {
    if (!composition) return;
    const totalDuration = localTimeline?.totalDurationSeconds || 3;
    const id = `${kind}_${Date.now()}`;
    const isClosing = kind === 'closing';
    const start = isClosing ? Math.max(0, totalDuration - 2.8) : 0.25;
    const end = isClosing ? Math.max(start + 0.5, totalDuration - 0.15) : Math.min(totalDuration - 0.1, 3);

    mutateComposition((draft) => {
      draft.text_layers.push({
        id,
        text: isClosing ? 'Tezlify AI Video Studio' : 'Yeni Başlık',
        start_time: Number(start.toFixed(2)),
        end_time: Number(Math.max(start + 0.5, end).toFixed(2)),
        anchor: isClosing ? 'bottom_center' : 'top_center',
        x_ratio: 0.5,
        y_ratio: isClosing ? 0.88 : 0.12,
        font_size: isClosing ? 40 : 64,
        color: '#FFFFFF',
        background_color: '#000000',
        background_opacity: isClosing ? 0.45 : 0.35,
        fade_in_seconds: 0.25,
        fade_out_seconds: 0.25,
        max_width_ratio: 0.84,
        bold: true,
      });
    });
  };

  const updateTextLayer = (index: number, changes: Partial<VideoComposition['text_layers'][number]>) => {
    mutateComposition((draft) => {
      draft.text_layers[index] = { ...draft.text_layers[index], ...changes };
    });
  };

  const removeTextLayer = (index: number) => {
    mutateComposition((draft) => {
      draft.text_layers.splice(index, 1);
    });
  };

  const saveComposition = async (): Promise<CompositionSummary | null> => {
    if (!selectedProjectId || !composition) return null;
    setIsSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const saved = await apiService.saveProjectComposition(selectedProjectId, composition);
      setSummary(saved);
      setComposition(saved.composition);
      setSceneDurations(
        Object.fromEntries(saved.timeline.map((entry) => [entry.scene_id, entry.duration_seconds]))
      );
      setIsDirty(false);
      setSuccessMessage('Kompozisyon kaydedildi.');
      onSummaryChange?.(saved);
      return saved;
    } catch (err: any) {
      setErrorMessage(err.message || 'Kompozisyon kaydedilemedi.');
      return null;
    } finally {
      setIsSaving(false);
    }
  };

  const startRender = async () => {
    if (!selectedProjectId || !composition) return;
    setIsStartingRender(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const saved = await saveComposition();
      if (!saved) return;

      const job = await apiService.startCompositionRender(selectedProjectId, saved.composition, {
        engineOverride: selectedEngine,
        synthesizeVoices,
      });
      setCurrentJob(job);
      const renderResponse = await apiService.listProjectRenders(selectedProjectId).catch(() => null);
      if (renderResponse) setRenders(renderResponse.items);
      setSuccessMessage('Kompozisyon render kuyruğuna alındı.');
      await onRendered?.();
    } catch (err: any) {
      setErrorMessage(err.message || 'Render başlatılamadı.');
    } finally {
      setIsStartingRender(false);
    }
  };

  if (isLoadingProjects) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner size="lg" />
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <EmptyState
        icon={Clapperboard}
        title="Henüz kompozisyon projesi yok"
        description="Önce Karakter & Animasyon stüdyosunda bir senaryo üretin. Oluşturulan SceneGraph sahneleri burada birleştirilebilir."
      />
    );
  }

  const isRendering = isActiveJob(currentJob);
  const activeFormat = composition?.format || '16:9';

  return (
    <div className="space-y-6">
      <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-4 border-b border-slate-200 dark:border-white/[0.08] pb-4">
        {!embedded ? (
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                <Clapperboard className="w-6 h-6 text-[#7367F0]" />
                Video Kompozisyon Stüdyosu
              </h1>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#7367F0]/10 text-[#7367F0] border border-[#7367F0]/20">
                Aşama 4.5
              </span>
              {summary && (
                <span
                  className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                    isDirty
                      ? 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-800'
                      : 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-800'
                  }`}
                >
                  {isDirty ? <RefreshCw className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
                  {isDirty ? 'Kaydedilmemiş değişiklikler' : 'Kayıtlı kompozisyon'}
                </span>
              )}
            </div>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Sahneleri sıralayın, geçişleri seçin, Türkçe metin ve altyazıları yönetin; tek bir MP4 olarak render edin.
            </p>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-sm font-bold text-slate-800 dark:text-white">
              <Clapperboard className="h-4 w-4 text-[#7367F0]" />
              Kompozisyon ayarları
            </span>
            {summary && (
              <span
                className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${
                  isDirty
                    ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300'
                    : 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300'
                }`}
              >
                {isDirty ? <RefreshCw className="h-3 w-3" /> : <CheckCircle2 className="h-3 w-3" />}
                {isDirty ? 'Kaydedilmemiş değişiklikler' : 'Kayıtlı kompozisyon'}
              </span>
            )}
          </div>
        )}

        <div className="flex flex-col sm:flex-row sm:items-center gap-2 w-full xl:w-auto">
          {!embedded && (
            <select
              aria-label="Proje seçimi"
              value={selectedProjectId}
              onChange={(event) => setSelectedProjectId(event.target.value)}
              className="h-9.5 rounded-lg border border-slate-200 dark:border-white/[0.12] bg-white dark:bg-[#2F3349] px-3 text-xs font-semibold text-slate-700 dark:text-slate-200 min-w-[220px]"
            >
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.title}
                </option>
              ))}
            </select>
          )}
          <Button
            variant="outline"
            size="md"
            onClick={saveComposition}
            disabled={!composition || isSaving || isRendering}
            className="gap-2"
          >
            {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Kaydet
          </Button>
          <Button
            size="md"
            onClick={startRender}
            disabled={!composition || isSaving || isStartingRender || isRendering}
            className="gap-2"
          >
            {isStartingRender ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Render Başlat
          </Button>
        </div>
      </div>

      {(errorMessage || successMessage) && (
        <div
          className={`flex items-start gap-2 rounded-xl border px-4 py-3 text-sm ${
            errorMessage
              ? 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-900'
              : 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900'
          }`}
        >
          {errorMessage ? <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" /> : <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />}
          <span>{errorMessage || successMessage}</span>
        </div>
      )}

      {isLoadingComposition || !composition ? (
        <div className="flex items-center justify-center py-20">
          <Spinner size="lg" />
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 items-start">
          <div className="xl:col-span-2 space-y-6">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2">
                  <Monitor className="w-4 h-4 text-[#7367F0]" />
                  Çıktı Formatı
                </CardTitle>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Format değiştiğinde kamera çerçevesi ve güvenli metin alanları otomatik uyarlanır.
                </p>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {FORMAT_OPTIONS.map((option) => {
                    const Icon = option.icon;
                    const selected = activeFormat === option.value;
                    return (
                      <button
                        key={option.value}
                        type="button"
                        aria-pressed={selected}
                        onClick={() => handleFormatChange(option.value)}
                        className={`flex items-center gap-3 rounded-xl border p-3 text-left transition-all ${
                          selected
                            ? 'border-[#7367F0] bg-[#7367F0]/10 text-[#7367F0] shadow-sm'
                            : 'border-slate-200 dark:border-white/[0.1] bg-white dark:bg-[#2F3349] text-slate-600 dark:text-slate-300 hover:border-[#7367F0]/50'
                        }`}
                      >
                        <div
                          className={`flex items-center justify-center rounded-lg ${
                            selected ? 'bg-[#7367F0] text-white' : 'bg-slate-100 dark:bg-white/[0.06]'
                          } ${option.value === '16:9' ? 'w-12 h-8' : option.value === '9:16' ? 'w-7 h-11' : 'w-9 h-9'}`}
                        >
                          <Icon className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-xs font-bold">{option.label}</div>
                          <div className="text-[11px] opacity-70">{option.hint}</div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3 flex flex-row items-start justify-between gap-4">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Layers className="w-4 h-4 text-[#7367F0]" />
                    Sahne Sırası ve Geçişler
                  </CardTitle>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Sahneleri yukarı/aşağı taşıyın. Her sahnenin geçişi bir sonraki sahneye uygulanır.
                  </p>
                </div>
                <span className="text-xs font-semibold text-slate-400 shrink-0">
                  {composition.scenes.length} sahne
                </span>
              </CardHeader>
              <CardContent className="space-y-3">
                {composition.scenes.map((scene, index) => {
                  const timelineEntry = localTimeline?.entries[index];
                  const sceneInfo = sceneLookup[scene.scene_id];
                  const hasDuration = scene.transition !== 'cut';
                  return (
                    <div
                      key={scene.scene_id}
                      data-testid={`scene-card-${scene.scene_id}`}
                      className="rounded-xl border border-slate-200 dark:border-white/[0.1] bg-slate-50/60 dark:bg-white/[0.02] p-3"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                        <div className="flex items-center gap-3 min-w-0 flex-1">
                          <div className="w-8 h-8 rounded-lg bg-[#7367F0] text-white flex items-center justify-center text-xs font-bold shrink-0">
                            {index + 1}
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-sm font-bold text-slate-800 dark:text-white">
                                {scene.scene_id}
                              </span>
                              <span className="text-[11px] font-medium text-slate-400">
                                {timelineEntry ? `${timelineEntry.duration_seconds.toFixed(1)} sn` : ''}
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                              {sceneInfo?.dialogue || 'Diyalog yok · sahne animasyonu'}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 flex-wrap">
                          <select
                            aria-label={`Sahne ${index + 1} geçişi`}
                            value={scene.transition}
                            onChange={(event) =>
                              updateSceneTransition(index, event.target.value as CompositionTransition)
                            }
                            className="h-8 rounded-lg border border-slate-200 dark:border-white/[0.12] bg-white dark:bg-[#2F3349] px-2 text-xs font-medium text-slate-700 dark:text-slate-200"
                          >
                            {Object.entries(TRANSITION_LABELS).map(([value, label]) => (
                              <option key={value} value={value}>
                                {label}
                              </option>
                            ))}
                          </select>
                          <div className="flex items-center gap-1">
                            <input
                              aria-label={`Sahne ${index + 1} geçiş süresi`}
                              type="number"
                              min={0.1}
                              max={5}
                              step={0.1}
                              disabled={!hasDuration}
                              value={scene.transition_duration_seconds}
                              onChange={(event) =>
                                updateSceneTransitionDuration(index, Number(event.target.value))
                              }
                              className="w-16 h-8 rounded-lg border border-slate-200 dark:border-white/[0.12] bg-white dark:bg-[#2F3349] px-2 text-xs disabled:opacity-40"
                            />
                            <span className="text-[11px] text-slate-400">sn</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Button
                              variant="outline"
                              size="icon"
                              aria-label={`Sahne ${index + 1}'i yukarı taşı`}
                              onClick={() => moveScene(index, -1)}
                              disabled={index === 0}
                              className="h-8 w-8"
                            >
                              <ArrowUp className="w-3.5 h-3.5" />
                            </Button>
                            <Button
                              variant="outline"
                              size="icon"
                              aria-label={`Sahne ${index + 1}'i aşağı taşı`}
                              onClick={() => moveScene(index, 1)}
                              disabled={index === composition.scenes.length - 1}
                              className="h-8 w-8"
                            >
                              <ArrowDown className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3 flex flex-row items-start justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Type className="w-4 h-4 text-[#7367F0]" />
                    Metin Katmanları
                  </CardTitle>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Açılış, sahne başlığı, karakter adı veya kapanış metni ekleyin. Türkçe karakterler desteklenir.
                  </p>
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button variant="outline" size="sm" onClick={() => addTextLayer('title')} className="gap-1">
                    <Plus className="w-3.5 h-3.5" />
                    Başlık
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => addTextLayer('closing')} className="gap-1">
                    <Plus className="w-3.5 h-3.5" />
                    Kapanış
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {composition.text_layers.length === 0 ? (
                  <p className="text-xs text-slate-500 dark:text-slate-400 rounded-xl border border-dashed border-slate-200 dark:border-white/[0.1] p-5 text-center">
                    Henüz metin katmanı yok. Başlık ekleyerek başlayın.
                  </p>
                ) : (
                  composition.text_layers.map((layer, index) => (
                    <div
                      key={layer.id}
                      className="rounded-xl border border-slate-200 dark:border-white/[0.1] bg-slate-50/60 dark:bg-white/[0.02] p-3 space-y-3"
                    >
                      <div className="flex items-center gap-2">
                        <Type className="w-4 h-4 text-[#7367F0] shrink-0" />
                        <input
                          aria-label={`Metin katmanı ${index + 1} içeriği`}
                          value={layer.text}
                          onChange={(event) => updateTextLayer(index, { text: event.target.value })}
                          className="flex-1 h-9 rounded-lg border border-slate-200 dark:border-white/[0.12] bg-white dark:bg-[#25293C] px-3 text-sm font-semibold text-slate-800 dark:text-white"
                        />
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Metin katmanı ${index + 1}'i sil`}
                          onClick={() => removeTextLayer(index)}
                          className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                          Başlangıç
                          <input
                            aria-label={`Metin katmanı ${index + 1} başlangıç`}
                            type="number"
                            min={0}
                            step={0.1}
                            value={layer.start_time}
                            onChange={(event) => updateTextLayer(index, { start_time: Number(event.target.value) })}
                            className="mt-1 w-full h-8 rounded-lg border border-slate-200 dark:border-white/[0.12] bg-white dark:bg-[#25293C] px-2 text-xs font-normal"
                          />
                        </label>
                        <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                          Bitiş
                          <input
                            aria-label={`Metin katmanı ${index + 1} bitiş`}
                            type="number"
                            min={0.1}
                            step={0.1}
                            value={layer.end_time}
                            onChange={(event) => updateTextLayer(index, { end_time: Number(event.target.value) })}
                            className="mt-1 w-full h-8 rounded-lg border border-slate-200 dark:border-white/[0.12] bg-white dark:bg-[#25293C] px-2 text-xs font-normal"
                          />
                        </label>
                        <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                          Konum
                          <select
                            aria-label={`Metin katmanı ${index + 1} konumu`}
                            value={layer.anchor}
                            onChange={(event) =>
                              updateTextLayer(index, { anchor: event.target.value as CompositionTextAnchor })
                            }
                            className="mt-1 w-full h-8 rounded-lg border border-slate-200 dark:border-white/[0.12] bg-white dark:bg-[#25293C] px-2 text-xs font-normal"
                          >
                            {ANCHOR_OPTIONS.map((anchor) => (
                              <option key={anchor.value} value={anchor.value}>
                                {anchor.label}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                          Punto
                          <input
                            aria-label={`Metin katmanı ${index + 1} punto`}
                            type="number"
                            min={8}
                            max={300}
                            value={layer.font_size}
                            onChange={(event) => updateTextLayer(index, { font_size: Number(event.target.value) })}
                            className="mt-1 w-full h-8 rounded-lg border border-slate-200 dark:border-white/[0.12] bg-white dark:bg-[#25293C] px-2 text-xs font-normal"
                          />
                        </label>
                      </div>

                      <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500 dark:text-slate-400">
                        <label className="flex items-center gap-1.5">
                          Renk
                          <input
                            aria-label={`Metin katmanı ${index + 1} rengi`}
                            type="color"
                            value={layer.color}
                            onChange={(event) => updateTextLayer(index, { color: event.target.value })}
                            className="w-8 h-7 rounded border border-slate-200 bg-transparent"
                          />
                        </label>
                        <label className="flex items-center gap-1.5">
                          Arka plan
                          <input
                            aria-label={`Metin katmanı ${index + 1} arka plan rengi`}
                            type="color"
                            value={layer.background_color || '#000000'}
                            onChange={(event) => updateTextLayer(index, { background_color: event.target.value })}
                            className="w-8 h-7 rounded border border-slate-200 bg-transparent"
                          />
                        </label>
                        <label className="flex items-center gap-1.5 flex-1 min-w-[140px]">
                          Arka plan opaklığı
                          <input
                            aria-label={`Metin katmanı ${index + 1} arka plan opaklığı`}
                            type="range"
                            min={0}
                            max={1}
                            step={0.05}
                            value={layer.background_opacity}
                            onChange={(event) =>
                              updateTextLayer(index, { background_opacity: Number(event.target.value) })
                            }
                            className="flex-1 accent-[#7367F0]"
                          />
                        </label>
                        <span className="text-[10px] font-semibold text-slate-400">
                          Fade {layer.fade_in_seconds.toFixed(1)}s / {layer.fade_out_seconds.toFixed(1)}s
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2">
                  <Captions className="w-4 h-4 text-[#7367F0]" />
                  Türkçe Altyazılar
                </CardTitle>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Altyazılar SceneDialogue metinlerinden ve gerçek ses süresinden üretilir. Fonem senkronizasyonu iddia edilmez.
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-4">
                  <label className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                    <input
                      aria-label="Altyazıları dahil et"
                      type="checkbox"
                      checked={composition.subtitles.enabled}
                      onChange={(event) =>
                        mutateComposition((draft) => {
                          draft.subtitles.enabled = event.target.checked;
                        })
                      }
                      className="w-4 h-4 accent-[#7367F0]"
                    />
                    Altyazıları dahil et
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                    <input
                      aria-label="Altyazıları videoya yak"
                      type="checkbox"
                      disabled={!composition.subtitles.enabled}
                      checked={composition.subtitles.burn_in}
                      onChange={(event) =>
                        mutateComposition((draft) => {
                          draft.subtitles.burn_in = event.target.checked;
                        })
                      }
                      className="w-4 h-4 accent-[#7367F0]"
                    />
                    Videoya yak (burn-in)
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                    <input
                      aria-label="SRT dosyasını kaydet"
                      type="checkbox"
                      disabled={!composition.subtitles.enabled}
                      checked={composition.subtitles.save_srt}
                      onChange={(event) =>
                        mutateComposition((draft) => {
                          draft.subtitles.save_srt = event.target.checked;
                        })
                      }
                      className="w-4 h-4 accent-[#7367F0]"
                    />
                    Ayrı SRT kaydet
                  </label>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                    Altyazı puntosu
                    <input
                      aria-label="Altyazı puntosu"
                      type="number"
                      min={12}
                      max={160}
                      disabled={!composition.subtitles.enabled}
                      value={composition.subtitles.font_size}
                      onChange={(event) =>
                        mutateComposition((draft) => {
                          draft.subtitles.font_size = Number(event.target.value);
                        })
                      }
                      className="mt-1 w-full h-9 rounded-lg border border-slate-200 dark:border-white/[0.12] bg-white dark:bg-[#25293C] px-3 text-sm font-normal disabled:opacity-50"
                    />
                  </label>
                  <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                    Alt güvenli alan
                    <input
                      aria-label="Altyazı alt güvenli alanı"
                      type="range"
                      min={0}
                      max={0.3}
                      step={0.01}
                      disabled={!composition.subtitles.enabled}
                      value={composition.subtitles.margin_bottom_ratio}
                      onChange={(event) =>
                        mutateComposition((draft) => {
                          draft.subtitles.margin_bottom_ratio = Number(event.target.value);
                        })
                      }
                      className="mt-2 w-full accent-[#7367F0] disabled:opacity-50"
                    />
                  </label>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2">
                  <Volume2 className="w-4 h-4 text-[#7367F0]" />
                  Ses Miksajı
                </CardTitle>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Diyalog sırası korunur; limiter kırpılmayı önler. Müzik otomatik üretilmez, yalnızca isteğe bağlı dosya kullanılır.
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-semibold text-slate-600 dark:text-slate-300 w-28 shrink-0">
                    Diyalog sesi
                  </span>
                  <input
                    aria-label="Diyalog ses seviyesi"
                    type="range"
                    min={-20}
                    max={12}
                    step={1}
                    value={composition.audio.dialogue_volume_db}
                    onChange={(event) =>
                      mutateComposition((draft) => {
                        draft.audio.dialogue_volume_db = Number(event.target.value);
                      })
                    }
                    className="flex-1 accent-[#7367F0]"
                  />
                  <span className="text-xs font-mono text-slate-500 w-14 text-right">
                    {composition.audio.dialogue_volume_db > 0 ? '+' : ''}
                    {composition.audio.dialogue_volume_db} dB
                  </span>
                </div>
                <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <input
                    aria-label="Limiter kullan"
                    type="checkbox"
                    checked={composition.audio.limiter_enabled}
                    onChange={(event) =>
                      mutateComposition((draft) => {
                        draft.audio.limiter_enabled = event.target.checked;
                      })
                    }
                    className="w-4 h-4 accent-[#7367F0]"
                  />
                  Limiter / tepe koruması etkin
                </label>
                <label className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                  Müzik dosyası (isteğe bağlı)
                  <input
                    aria-label="Müzik dosyası"
                    type="text"
                    value={composition.audio.music_file || ''}
                    onChange={(event) =>
                      mutateComposition((draft) => {
                        draft.audio.music_file = event.target.value.trim() || null;
                      })
                    }
                    placeholder="Örn. /Users/.../muzik.mp3 — boş bırakılabilir"
                    className="mt-1 w-full h-9 rounded-lg border border-slate-200 dark:border-white/[0.12] bg-white dark:bg-[#25293C] px-3 text-sm font-normal"
                  />
                </label>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6 xl:sticky xl:top-6">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2">
                  <Film className="w-4 h-4 text-[#7367F0]" />
                  Zaman Çizelgesi Önizlemesi
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-xl bg-slate-900 p-3 text-white">
                  <div className="flex items-center justify-between text-[11px] text-slate-400 mb-2">
                    <span>{activeFormat} · {composition.width} × {composition.height}</span>
                    <span>{formatCompositionSeconds(localTimeline?.totalDurationSeconds || 0)}</span>
                  </div>
                  <div className="flex h-10 w-full overflow-hidden rounded-lg bg-slate-800">
                    {(localTimeline?.entries || []).map((entry, index) => (
                      <div
                        key={entry.scene_id}
                        className="flex min-w-0 items-center justify-center border-r border-slate-900/60 last:border-r-0 px-1"
                        style={{
                          width: `${Math.max(
                            12,
                            (entry.duration_seconds /
                              Math.max(1, localTimeline?.totalDurationSeconds || 1)) *
                              100
                          )}%`,
                          backgroundColor: index % 2 === 0 ? '#7367F0' : '#8F86F4',
                        }}
                        title={`${entry.scene_id} · ${entry.start_time.toFixed(1)}s - ${entry.end_time.toFixed(1)}s`}
                      >
                        <span className="truncate text-[10px] font-bold text-white/90">{entry.order}</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-2 flex items-center justify-between text-[10px] text-slate-400">
                    <span>{summary?.scene_count || composition.scenes.length} sahne</span>
                    <span>{composition.text_layers.length} metin</span>
                    <span>
                      {localTimeline?.entries.filter((entry) => entry.transition !== 'cut').length || 0} geçiş
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded-lg bg-slate-50 dark:bg-white/[0.03] p-2.5">
                    <div className="text-slate-400 text-[10px] font-semibold uppercase">Süre</div>
                    <div className="font-bold text-slate-800 dark:text-white">
                      {formatCompositionSeconds(localTimeline?.totalDurationSeconds || 0)}
                    </div>
                  </div>
                  <div className="rounded-lg bg-slate-50 dark:bg-white/[0.03] p-2.5">
                    <div className="text-slate-400 text-[10px] font-semibold uppercase">Çözünürlük</div>
                    <div className="font-bold text-slate-800 dark:text-white">
                      {composition.width}×{composition.height}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2">
                  <Play className="w-4 h-4 text-[#7367F0]" />
                  Render
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <label className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                  Render motoru
                  <select
                    aria-label="Render motoru"
                    value={selectedEngine}
                    onChange={(event) =>
                      setSelectedEngine(event.target.value as 'BLENDER_WORKBENCH' | 'BLENDER_EEVEE')
                    }
                    className="mt-1 w-full h-9 rounded-lg border border-slate-200 dark:border-white/[0.12] bg-white dark:bg-[#25293C] px-3 text-sm font-normal"
                  >
                    <option value="BLENDER_WORKBENCH">Blender Workbench</option>
                    <option value="BLENDER_EEVEE">Blender EEVEE</option>
                  </select>
                </label>

                <div>
                  <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                    <input
                      aria-label="Sesleri sentezle"
                      type="checkbox"
                      checked={synthesizeVoices}
                      onChange={(event) => setSynthesizeVoices(event.target.checked)}
                      className="w-4 h-4 accent-[#7367F0]"
                    />
                    ElevenLabs seslerini sentezle
                  </label>
                  {voiceStatus && !voiceStatus.is_configured && (
                    <p className="mt-1.5 flex items-start gap-1.5 text-[11px] text-amber-600 dark:text-amber-400">
                      <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                      ELEVENLABS_API_KEY tanımlı değil. Ses sentezi gerçek ElevenLabs çıktısı üretemez.
                    </p>
                  )}
                </div>

                <Button
                  size="md"
                  onClick={startRender}
                  disabled={isSaving || isStartingRender || isRendering}
                  className="w-full gap-2"
                >
                  {isStartingRender || isRendering ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  {isRendering ? 'Render devam ediyor' : 'Kompozisyonu Render Et'}
                </Button>

                {currentJob && (
                  <div className="rounded-xl border border-slate-200 dark:border-white/[0.1] p-3 space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <StatusBadge
                        status={
                          currentJob.status === 'completed'
                            ? 'ready'
                            : currentJob.status === 'running'
                            ? 'processing'
                            : currentJob.status === 'failed'
                            ? 'failed'
                            : 'pending'
                        }
                      />
                      <span className="text-[10px] font-mono text-slate-400">{currentJob.id}</span>
                    </div>
                    <Progress value={currentJob.progress_percent} />
                    <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
                      <span className="truncate">{currentJob.current_step || currentJob.status}</span>
                      <span className="font-semibold">{Math.round(currentJob.progress_percent)}%</span>
                    </div>
                    {currentJob.error_message && (
                      <p className="text-[11px] text-red-600 dark:text-red-400">{currentJob.error_message}</p>
                    )}
                    {currentJob.status === 'completed' && currentJob.output_video_path && (
                      <div className="space-y-2">
                        <video
                          key={currentJob.id}
                          controls
                          preload="metadata"
                          src={apiService.getRenderVideoUrl(currentJob.id)}
                          className="w-full rounded-lg bg-black max-h-72"
                        />
                        <div className="flex flex-wrap gap-2">
                          <a
                            href={apiService.getRenderVideoUrl(currentJob.id)}
                            download
                            className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#7367F0] hover:underline"
                          >
                            <Download className="w-3.5 h-3.5" />
                            MP4 indir
                          </a>
                          {currentJob.output_metadata?.subtitle_file_path && (
                            <a
                              href={apiService.getRenderSubtitlesUrl(currentJob.id)}
                              className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#7367F0] hover:underline"
                            >
                              <Captions className="w-3.5 h-3.5" />
                              SRT indir ({currentJob.output_metadata.subtitle_cue_count || 0} cue)
                            </a>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            {renders.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle>Render Geçmişi</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {renders.slice(0, 6).map((render) => (
                    <button
                      key={render.id}
                      type="button"
                      onClick={() => setCurrentJob(render)}
                      className={`w-full rounded-lg border p-2.5 text-left transition-colors ${
                        currentJob?.id === render.id
                          ? 'border-[#7367F0] bg-[#7367F0]/10'
                          : 'border-slate-200 dark:border-white/[0.08] hover:bg-slate-50 dark:hover:bg-white/[0.03]'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-semibold text-slate-700 dark:text-slate-200 truncate">
                          {render.output_metadata?.composition_name || render.id}
                        </span>
                        <span className="text-[10px] text-slate-400">{Math.round(render.progress_percent)}%</span>
                      </div>
                      <div className="flex items-center justify-between gap-2 mt-1 text-[10px] text-slate-400">
                        <span>{render.status}</span>
                        <span>
                          {render.output_metadata?.duration_seconds
                            ? formatCompositionSeconds(render.output_metadata.duration_seconds)
                            : '—'}
                        </span>
                      </div>
                    </button>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
