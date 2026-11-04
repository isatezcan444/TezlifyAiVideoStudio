import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  CheckCircle2,
  Clapperboard,
  Clock3,
  Loader2,
  Plus,
  RefreshCw,
  Save,
  Trash2,
  User,
  Video,
} from 'lucide-react';
import {
  RenderJob,
  SceneGraph,
  SceneGraphDialogue,
  SceneGraphScene,
  StudioProject,
} from '../../../types/studio';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { StudioAlert, StudioSectionTitle } from '../StudioShared';
import { latestRenderForProject, renderKindLabel } from '../../../lib/studioWorkspace';
import { apiService } from '../../../services/api';

interface ScenesStepProps {
  project: StudioProject;
  renders: RenderJob[];
  onSaveSceneGraph: (sceneGraph: SceneGraph) => Promise<StudioProject>;
  onNext: () => void;
}

function cloneSceneGraph(sceneGraph: SceneGraph): SceneGraph {
  return JSON.parse(JSON.stringify(sceneGraph)) as SceneGraph;
}

function nextSceneId(scenes: SceneGraphScene[]): string {
  const numericIds = scenes
    .map((scene) => Number(scene.scene_id.replace(/\D/g, '')))
    .filter((value) => Number.isFinite(value));
  const next = numericIds.length > 0 ? Math.max(...numericIds) + 1 : scenes.length + 1;
  return `scene_${String(next).padStart(2, '0')}`;
}

export const ScenesStep: React.FC<ScenesStepProps> = ({
  project,
  renders,
  onSaveSceneGraph,
  onNext,
}) => {
  const [draft, setDraft] = useState<SceneGraph | null>(
    project.scene_graph ? cloneSceneGraph(project.scene_graph) : null
  );
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setDraft(project.scene_graph ? cloneSceneGraph(project.scene_graph) : null);
    setError(null);
    setMessage(null);
  }, [project.id, project.scene_graph]);

  const latestAnimation = useMemo(
    () => latestRenderForProject(renders, project.id, 'animation'),
    [project.id, renders]
  );
  const latestAnyRender = useMemo(
    () => latestRenderForProject(renders, project.id),
    [project.id, renders]
  );

  const isDirty = useMemo(() => {
    if (!draft || !project.scene_graph) return false;
    return JSON.stringify(draft) !== JSON.stringify(project.scene_graph);
  }, [draft, project.scene_graph]);

  const mutate = (mutator: (next: SceneGraph) => void) => {
    setDraft((previous) => {
      if (!previous) return previous;
      const next = cloneSceneGraph(previous);
      mutator(next);
      return next;
    });
    setMessage(null);
    setError(null);
  };

  const moveScene = (index: number, direction: -1 | 1) => {
    if (!draft) return;
    const target = index + direction;
    if (target < 0 || target >= draft.scenes.length) return;
    mutate((next) => {
      const [moved] = next.scenes.splice(index, 1);
      next.scenes.splice(target, 0, moved);
      next.scenes.forEach((scene, sceneIndex) => {
        scene.sequence_order = sceneIndex + 1;
      });
    });
  };

  const updateScene = (sceneIndex: number, updates: Partial<SceneGraphScene>) => {
    mutate((next) => {
      next.scenes[sceneIndex] = { ...next.scenes[sceneIndex], ...updates };
    });
  };

  const updateDialogue = (
    sceneIndex: number,
    dialogueIndex: number,
    updates: Partial<SceneGraphDialogue>
  ) => {
    mutate((next) => {
      next.scenes[sceneIndex].dialogues[dialogueIndex] = {
        ...next.scenes[sceneIndex].dialogues[dialogueIndex],
        ...updates,
      };
    });
  };

  const addDialogue = (sceneIndex: number) => {
    if (!draft || draft.characters.length === 0) {
      setError('Diyalog eklemek için proje kadrosunda en az bir karakter olmalıdır.');
      return;
    }
    mutate((next) => {
      const scene = next.scenes[sceneIndex];
      const endTime = Math.max(1, Math.min(scene.duration_seconds, 3));
      scene.dialogues.push({
        character_id: next.characters[0].id,
        start_time: 0,
        end_time: endTime,
        text: 'Yeni diyalog',
        visemes: [],
      });
    });
  };

  const removeDialogue = (sceneIndex: number, dialogueIndex: number) => {
    mutate((next) => {
      next.scenes[sceneIndex].dialogues.splice(dialogueIndex, 1);
    });
  };

  const addScene = () => {
    if (!draft || draft.characters.length === 0) return;
    const sceneId = nextSceneId(draft.scenes);
    mutate((next) => {
      next.scenes.push({
        scene_id: sceneId,
        sequence_order: next.scenes.length + 1,
        duration_seconds: 5,
        background: { type: 'preset', asset_id: 'bg_modern_cafe', lighting: 'warm_interior' },
        camera: { angle: 'medium_shot', fov: 45, movement: 'static' },
        character_placements: next.characters.map((character, index) => ({
          character_id: character.id,
          position: [(index - (next.characters.length - 1) / 2) * 1.2, 0, 0] as [number, number, number],
          rotation_y: index % 2 === 0 ? 25 : -25,
          pose: 'standing',
          expression: 'neutral',
        })),
        dialogues: [],
        transition: { type: 'cut', duration_seconds: 0 },
      });
    });
  };

  const removeScene = (sceneIndex: number) => {
    if (!draft || draft.scenes.length <= 1) {
      setError('SceneGraph en az bir sahne içermelidir.');
      return;
    }
    mutate((next) => {
      next.scenes.splice(sceneIndex, 1);
      next.scenes.forEach((scene, index) => {
        scene.sequence_order = index + 1;
      });
    });
  };

  const validateDraft = (graph: SceneGraph): string | null => {
    if (graph.scenes.length === 0) return 'En az bir sahne gerekli.';
    for (const scene of graph.scenes) {
      if (scene.duration_seconds <= 0) {
        return `${scene.scene_id}: sahne süresi sıfırdan büyük olmalıdır.`;
      }
      for (const dialogue of scene.dialogues) {
        if (dialogue.end_time <= dialogue.start_time) {
          return `${scene.scene_id}: diyalog bitişi başlangıçtan büyük olmalıdır.`;
        }
        if (dialogue.end_time > scene.duration_seconds) {
          return `${scene.scene_id}: diyalog bitişi sahne süresini aşamaz.`;
        }
      }
    }
    return null;
  };

  const save = async () => {
    if (!draft) return;
    const validationError = validateDraft(draft);
    if (validationError) {
      setError(validationError);
      return;
    }
    setIsSaving(true);
    setError(null);
    setMessage(null);
    try {
      await onSaveSceneGraph(draft);
      setMessage('Sahne düzenlemeleri kaydedildi.');
    } catch (err: any) {
      setError(err.message || 'Sahne düzenlemeleri kaydedilemedi.');
    } finally {
      setIsSaving(false);
    }
  };

  if (!draft) {
    return (
      <StudioAlert tone="warning">
        Projede SceneGraph bulunmuyor. Hikâye adımından bir senaryo üretin.
      </StudioAlert>
    );
  }

  return (
    <div className="space-y-5">
      <StudioSectionTitle
        title="Sahne editörü"
        description="Sahne sırasını, süresini ve diyaloglarını düzenleyin. Değişiklikler backend SceneGraph sözleşmesine kaydedilir."
        action={
          <div className="flex flex-wrap items-center gap-2">
            {isDirty ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[10px] font-bold text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
                <RefreshCw className="h-3 w-3" />
                Kaydedilmemiş
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
                <CheckCircle2 className="h-3 w-3" />
                Kayıtlı
              </span>
            )}
            <Button size="sm" onClick={save} disabled={!isDirty || isSaving} className="gap-1.5">
              {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              Kaydet
            </Button>
          </div>
        }
      />

      {error && <StudioAlert tone="error">{error}</StudioAlert>}
      {message && <StudioAlert tone="success">{message}</StudioAlert>}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-4">
        <div className="space-y-3 xl:col-span-3">
          {draft.scenes.map((scene, sceneIndex) => (
            <Card key={scene.scene_id} data-testid={`workflow-scene-${scene.scene_id}`}>
              <CardHeader className="flex-row items-start justify-between gap-3 pb-3">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#7367F0] text-xs font-extrabold text-white">
                    {sceneIndex + 1}
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <CardTitle className="text-sm">{scene.scene_id}</CardTitle>
                      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500 dark:bg-white/[0.06] dark:text-slate-300">
                        <Clock3 className="h-3 w-3" />
                        {scene.duration_seconds.toFixed(1)} sn
                      </span>
                    </div>
                    <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                      {scene.background.asset_id} · {scene.camera.angle.replace(/_/g, ' ')} ·{' '}
                      {scene.character_placements.length} yerleşim
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => moveScene(sceneIndex, -1)}
                    disabled={sceneIndex === 0}
                    aria-label={`${scene.scene_id} sahnesini yukarı taşı`}
                    className="h-7 w-7"
                  >
                    <ArrowUp className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => moveScene(sceneIndex, 1)}
                    disabled={sceneIndex === draft.scenes.length - 1}
                    aria-label={`${scene.scene_id} sahnesini aşağı taşı`}
                    className="h-7 w-7"
                  >
                    <ArrowDown className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removeScene(sceneIndex)}
                    disabled={draft.scenes.length <= 1}
                    aria-label={`${scene.scene_id} sahnesini sil`}
                    className="h-7 w-7 text-red-500 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/30"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
                    Sahne süresi (sn)
                    <input
                      type="number"
                      min={0.1}
                      step={0.1}
                      value={scene.duration_seconds}
                      onChange={(event) =>
                        updateScene(sceneIndex, {
                          duration_seconds: Math.max(0.1, Number(event.target.value) || 0.1),
                        })
                      }
                      className="vuexy-input mt-1 h-8 w-full px-2 text-xs font-normal"
                    />
                  </label>
                  <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
                    Arka plan asset
                    <input
                      type="text"
                      value={scene.background.asset_id}
                      onChange={(event) =>
                        updateScene(sceneIndex, {
                          background: { ...scene.background, asset_id: event.target.value },
                        })
                      }
                      className="vuexy-input mt-1 h-8 w-full px-2 text-xs font-normal"
                    />
                  </label>
                  <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
                    Kamera açısı
                    <input
                      type="text"
                      value={scene.camera.angle}
                      onChange={(event) =>
                        updateScene(sceneIndex, {
                          camera: { ...scene.camera, angle: event.target.value },
                        })
                      }
                      className="vuexy-input mt-1 h-8 w-full px-2 text-xs font-normal"
                    />
                  </label>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  {scene.character_placements.map((placement) => {
                    const character = draft.characters.find(
                      (item) => item.id === placement.character_id
                    );
                    return (
                      <span
                        key={placement.character_id}
                        className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-2 py-0.5 text-[10px] font-semibold text-slate-600 dark:border-white/[0.1] dark:text-slate-300"
                      >
                        <User className="h-3 w-3 text-[#7367F0]" />
                        {character?.name || placement.character_id}
                      </span>
                    );
                  })}
                  {scene.character_placements.length === 0 && (
                    <span className="text-[10px] text-amber-600 dark:text-amber-400">
                      Bu sahnede karakter yerleşimi yok.
                    </span>
                  )}
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
                      Diyaloglar ({scene.dialogues.length})
                    </span>
                    <button
                      type="button"
                      onClick={() => addDialogue(sceneIndex)}
                      className="inline-flex items-center gap-1 text-[10px] font-bold text-[#7367F0] hover:underline"
                    >
                      <Plus className="h-3 w-3" />
                      Diyalog ekle
                    </button>
                  </div>
                  {scene.dialogues.length === 0 && (
                    <p className="rounded-lg border border-dashed border-slate-200 p-3 text-center text-[10px] text-slate-400 dark:border-white/[0.1]">
                      Bu sahnede diyalog yok.
                    </p>
                  )}
                  {scene.dialogues.map((dialogue, dialogueIndex) => (
                    <div
                      key={`${scene.scene_id}-dialogue-${dialogueIndex}`}
                      className="rounded-lg border border-slate-200 p-2.5 dark:border-white/[0.08]"
                    >
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-12">
                        <label className="text-[10px] font-bold text-slate-500 sm:col-span-3">
                          Konuşmacı
                          <select
                            value={dialogue.character_id}
                            onChange={(event) =>
                              updateDialogue(sceneIndex, dialogueIndex, {
                                character_id: event.target.value,
                              })
                            }
                            className="vuexy-input mt-1 h-8 w-full px-1.5 text-[11px] font-normal"
                          >
                            {draft.characters.map((character) => (
                              <option key={character.id} value={character.id}>
                                {character.name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="text-[10px] font-bold text-slate-500 sm:col-span-2">
                          Başlangıç
                          <input
                            type="number"
                            min={0}
                            step={0.1}
                            value={dialogue.start_time}
                            onChange={(event) =>
                              updateDialogue(sceneIndex, dialogueIndex, {
                                start_time: Math.max(0, Number(event.target.value) || 0),
                              })
                            }
                            className="vuexy-input mt-1 h-8 w-full px-1.5 text-[11px] font-normal"
                          />
                        </label>
                        <label className="text-[10px] font-bold text-slate-500 sm:col-span-2">
                          Bitiş
                          <input
                            type="number"
                            min={0.1}
                            step={0.1}
                            value={dialogue.end_time}
                            onChange={(event) =>
                              updateDialogue(sceneIndex, dialogueIndex, {
                                end_time: Math.max(0.1, Number(event.target.value) || 0.1),
                              })
                            }
                            className="vuexy-input mt-1 h-8 w-full px-1.5 text-[11px] font-normal"
                          />
                        </label>
                        <label className="text-[10px] font-bold text-slate-500 sm:col-span-5">
                          Metin
                          <div className="mt-1 flex gap-1">
                            <input
                              type="text"
                              value={dialogue.text}
                              onChange={(event) =>
                                updateDialogue(sceneIndex, dialogueIndex, {
                                  text: event.target.value,
                                })
                              }
                              className="vuexy-input h-8 min-w-0 flex-1 px-2 text-[11px] font-normal"
                            />
                            <button
                              type="button"
                              onClick={() => removeDialogue(sceneIndex, dialogueIndex)}
                              aria-label="Diyaloğu sil"
                              className="rounded-lg p-1.5 text-red-400 transition hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/30"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </label>
                      </div>
                      <div className="mt-1 flex items-center gap-1 text-[9px] text-slate-400">
                        {dialogue.audio_file ? (
                          <>
                            <Video className="h-3 w-3" />
                            Mevcut/önbellek ses dosyası: {dialogue.audio_file.split('/').pop()}
                          </>
                        ) : (
                          <>
                            <AlertCircle className="h-3 w-3" />
                            Ses dosyası yok — render sırasında sentezlenecek veya sessiz kalacak.
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}

          <Button variant="outline" size="md" onClick={addScene} className="w-full gap-2">
            <Plus className="h-4 w-4" />
            Sahne ekle
          </Button>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2">
                <Clapperboard className="h-4 w-4 text-[#7367F0]" />
                Sahne önizlemesi
              </CardTitle>
            </CardHeader>
            <CardContent>
              {latestAnimation?.status === 'completed' ? (
                <div className="space-y-2">
                  <video
                    controls
                    preload="metadata"
                    src={apiService.getRenderVideoUrl(latestAnimation.id)}
                    className="w-full rounded-lg bg-black"
                  />
                  <p className="text-[10px] text-slate-400">
                    Son animasyon render’ı · {renderKindLabel(latestAnimation)}
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-3 gap-1.5 rounded-xl bg-slate-950 p-2">
                  {draft.scenes.slice(0, 6).map((scene, index) => (
                    <div
                      key={scene.scene_id}
                      className="flex h-20 min-w-0 items-end rounded-lg px-1.5 py-1.5"
                      style={{
                        background:
                          index % 2 === 0
                            ? 'linear-gradient(145deg, #423a74, #2e294c)'
                            : 'linear-gradient(145deg, #243f4a, #1f2b35)',
                      }}
                    >
                      <div className="min-w-0">
                        <div className="truncate text-[9px] font-bold text-white/90">{scene.scene_id}</div>
                        <div className="truncate text-[8px] text-white/50">
                          {scene.dialogues[0]?.text || 'Sahne'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Render durumu</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between gap-2 text-[11px]">
                <span className="text-slate-500 dark:text-slate-400">Proje render durumu</span>
                <span className="font-bold text-slate-700 dark:text-slate-200">
                  {latestAnyRender?.status || 'Kayıt yok'}
                </span>
              </div>
              {latestAnyRender && (
                <div className="rounded-lg bg-slate-50 p-2 text-[10px] text-slate-500 dark:bg-white/[0.03] dark:text-slate-400">
                  {renderKindLabel(latestAnyRender)} · {latestAnyRender.current_step}
                </div>
              )}
              <p className="text-[10px] leading-relaxed text-slate-400">
                Backend, render durumunu proje/iş seviyesinde tutar; sahne başına ayrı durum alanı
                döndürmez. Bu yüzden burada proje render durumu gösterilir.
              </p>
              {latestAnyRender?.status === 'failed' && latestAnyRender.error_message && (
                <details className="text-[10px] text-red-600 dark:text-red-400">
                  <summary className="cursor-pointer font-bold">Hata ayrıntısı</summary>
                  <p className="mt-1 whitespace-pre-wrap break-words">{latestAnyRender.error_message}</p>
                </details>
              )}
            </CardContent>
          </Card>

          <Button variant="outline" size="md" onClick={onNext} className="w-full gap-2">
            Animasyon adımına geç
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};
