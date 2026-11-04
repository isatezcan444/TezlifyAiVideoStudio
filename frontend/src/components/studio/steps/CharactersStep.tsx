import React, { useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  Edit2,
  ExternalLink,
  Loader2,
  Mic,
  Plus,
  Sparkles,
  UserPlus,
  Users,
  Volume2,
  X,
} from 'lucide-react';
import {
  Character,
  SceneGraph,
  SceneGraphCharacter,
  StudioProject,
  VoiceProfile,
  VoiceStatusResponse,
} from '../../../types/studio';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { Modal } from '../../ui/Modal';
import { StudioAlert, StudioSectionTitle } from '../StudioShared';

interface CharactersStepProps {
  project: StudioProject;
  library: Character[];
  voices: VoiceProfile[];
  voiceStatus: VoiceStatusResponse | null;
  onSaveSceneGraph: (sceneGraph: SceneGraph) => Promise<StudioProject>;
  onCreateCharacter: (data: Partial<Character>) => Promise<Character>;
  onUpdateCharacter: (id: string, data: Partial<Character>) => Promise<Character>;
  onOpenCharacterStudio: () => void;
  onNext: () => void;
}

function styleFromCharacter(character: Character): SceneGraphCharacter['style'] {
  return {
    hair_color: character.palette.hair_color,
    skin_tone: character.palette.skin_tone,
    shirt_color: character.palette.shirt_color,
    pants_color: character.palette.pants_color,
  };
}

export const CharactersStep: React.FC<CharactersStepProps> = ({
  project,
  library,
  voices,
  voiceStatus,
  onSaveSceneGraph,
  onCreateCharacter,
  onUpdateCharacter,
  onOpenCharacterStudio,
  onNext,
}) => {
  const [isSaving, setIsSaving] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingCharacter, setEditingCharacter] = useState<SceneGraphCharacter | null>(null);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isUpdatingCharacter, setIsUpdatingCharacter] = useState(false);
  const [editForm, setEditForm] = useState({
    name: '',
    voice_id: '',
    hair_color: '#2C1810',
    skin_tone: '#F5D0A9',
    shirt_color: '#3B82F6',
    pants_color: '#1E293B',
  });
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [newCharacter, setNewCharacter] = useState({
    name: '',
    description: '',
    gender: 'neutral' as Character['gender'],
    voice_id: voices[0]?.voice_id || '',
  });

  const sceneGraph = project.scene_graph;
  const cast = sceneGraph?.characters || [];
  const scenes = sceneGraph?.scenes || [];
  const castIds = new Set(cast.map((character) => character.id));
  const availableCharacters = library.filter((character) => !castIds.has(character.id));

  const saveGraph = async (nextGraph: SceneGraph, successMessage: string) => {
    setIsSaving(true);
    setError(null);
    setMessage(null);
    try {
      await onSaveSceneGraph(nextGraph);
      setMessage(successMessage);
    } catch (err: any) {
      setError(err.message || 'Karakter değişiklikleri kaydedilemedi.');
      throw err;
    } finally {
      setIsSaving(false);
    }
  };

  const addCharacter = async (character: Character) => {
    if (!sceneGraph) return;
    const nextGraph: SceneGraph = JSON.parse(JSON.stringify(sceneGraph));
    nextGraph.characters.push({
      id: character.id,
      name: character.name,
      voice_id: character.voice_id || voices[0]?.voice_id || 'tr_yelda',
      style: styleFromCharacter(character),
    });
    try {
      await saveGraph(nextGraph, `${character.name} proje kadrosuna eklendi.`);
    } catch {
      // Error already surfaced by saveGraph.
    }
  };

  const removeCharacter = async (characterId: string) => {
    if (!sceneGraph) return;
    const isReferenced = scenes.some(
      (scene) =>
        scene.character_placements.some((placement) => placement.character_id === characterId) ||
        scene.dialogues.some((dialogue) => dialogue.character_id === characterId)
    );
    if (isReferenced) {
      setError('Bu karakter sahnelerde kullanılıyor. Önce sahne yerleşimlerini ve diyalogları düzenleyin.');
      return;
    }
    if (cast.length <= 1) {
      setError('SceneGraph en az bir karakter içermelidir.');
      return;
    }
    const nextGraph: SceneGraph = JSON.parse(JSON.stringify(sceneGraph));
    nextGraph.characters = nextGraph.characters.filter((character) => character.id !== characterId);
    try {
      await saveGraph(nextGraph, 'Karakter proje kadrosundan çıkarıldı.');
    } catch {
      // Error already surfaced by saveGraph.
    }
  };

  const updateVoice = async (characterId: string, voiceId: string) => {
    if (!sceneGraph) return;
    const nextGraph: SceneGraph = JSON.parse(JSON.stringify(sceneGraph));
    const character = nextGraph.characters.find((item) => item.id === characterId);
    if (!character) return;
    character.voice_id = voiceId;
    try {
      await saveGraph(nextGraph, `${character.name} için ses profili güncellendi.`);
    } catch {
      // Error already surfaced by saveGraph.
    }
  };

  const createAndAdd = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!newCharacter.name.trim()) {
      setError('Karakter adı zorunludur.');
      return;
    }
    setIsCreating(true);
    setError(null);
    try {
      const created = await onCreateCharacter({
        name: newCharacter.name.trim(),
        description: newCharacter.description.trim(),
        gender: newCharacter.gender,
        voice_id: newCharacter.voice_id,
      });
      await addCharacter(created);
      setIsCreateOpen(false);
      setNewCharacter({
        name: '',
        description: '',
        gender: 'neutral',
        voice_id: voices[0]?.voice_id || '',
      });
    } catch (err: any) {
      setError(err.message || 'Karakter oluşturulamadı.');
    } finally {
      setIsCreating(false);
    }
  };

  const openEdit = (character: SceneGraphCharacter) => {
    setEditingCharacter(character);
    setEditForm({
      name: character.name,
      voice_id: character.voice_id,
      hair_color: character.style.hair_color,
      skin_tone: character.style.skin_tone,
      shirt_color: character.style.shirt_color,
      pants_color: character.style.pants_color,
    });
    setError(null);
    setIsEditOpen(true);
  };

  const saveCharacterEdit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!sceneGraph || !editingCharacter) return;
    if (!editForm.name.trim()) {
      setError('Karakter adı zorunludur.');
      return;
    }
    setIsUpdatingCharacter(true);
    setError(null);
    setMessage(null);
    try {
      const libraryMatch = library.find((item) => item.id === editingCharacter.id);
      if (libraryMatch) {
        const palette = { ...libraryMatch.palette };
        await onUpdateCharacter(editingCharacter.id, {
          name: editForm.name.trim(),
          voice_id: editForm.voice_id,
          palette: {
            ...palette,
            hair_color: editForm.hair_color,
            skin_tone: editForm.skin_tone,
            shirt_color: editForm.shirt_color,
            pants_color: editForm.pants_color,
          },
        });
      }
      const nextGraph = JSON.parse(JSON.stringify(sceneGraph)) as SceneGraph;
      const castCharacter = nextGraph.characters.find(
        (character) => character.id === editingCharacter.id
      );
      if (castCharacter) {
        castCharacter.name = editForm.name.trim();
        castCharacter.voice_id = editForm.voice_id;
        castCharacter.style = {
          hair_color: editForm.hair_color,
          skin_tone: editForm.skin_tone,
          shirt_color: editForm.shirt_color,
          pants_color: editForm.pants_color,
        };
      }
      await saveGraph(nextGraph, `${editForm.name.trim()} karakteri güncellendi.`);
      setIsEditOpen(false);
      setEditingCharacter(null);
    } catch (err: any) {
      setError(err.message || 'Karakter güncellenemedi.');
    } finally {
      setIsUpdatingCharacter(false);
    }
  };

  return (
    <div className="space-y-5">
      <StudioSectionTitle
        title="Karakterler ve ses profilleri"
        description="Proje kadrosunu yönetin, görünümü ve ses profilini belirleyin. ElevenLabs bağlantısı yalnızca gerçekten yapılandırıldıysa bağlı gösterilir."
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={onOpenCharacterStudio} className="gap-1.5">
              <ExternalLink className="h-3.5 w-3.5" />
              Karakter Stüdyosu
            </Button>
            <Button size="sm" onClick={() => setIsCreateOpen(true)} className="gap-1.5">
              <UserPlus className="h-3.5 w-3.5" />
              Yeni karakter
            </Button>
          </div>
        }
      />

      {error && <StudioAlert tone="error">{error}</StudioAlert>}
      {message && <StudioAlert tone="success">{message}</StudioAlert>}

      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
                  voiceStatus?.is_configured
                    ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-300'
                    : 'bg-amber-100 text-amber-600 dark:bg-amber-950/50 dark:text-amber-300'
                }`}
              >
                <Mic className="h-4 w-4" />
              </div>
              <div>
                <div className="text-xs font-bold text-slate-800 dark:text-white">
                  Ses kaynağı: {voiceStatus?.is_configured ? 'ElevenLabs bağlı' : 'ElevenLabs yapılandırılmadı'}
                </div>
                <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
                  {voiceStatus?.is_configured
                    ? `Model: ${voiceStatus.default_model} · ${voices.length} ses profili kullanılabilir.`
                    : 'ELEVENLABS_API_KEY tanımlı değil. Katalogdaki sesler görüntülenebilir, ancak yeni ses üretimi yapılamaz; mevcut ses dosyaları kullanılır.'}
                </p>
              </div>
            </div>
            {!voiceStatus?.is_configured && (
              <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[10px] font-bold text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
                <AlertCircle className="h-3 w-3" />
                Bağlantı yok
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <div className="flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-sm font-bold text-slate-800 dark:text-white">
              <Users className="h-4 w-4 text-[#7367F0]" />
              Proje kadrosu ({cast.length})
            </h3>
          </div>

          {cast.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-xs text-slate-400 dark:border-white/[0.1]">
              Proje kadrosu boş. Kütüphaneden karakter ekleyin.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {cast.map((character) => {
                const libraryMatch = library.find((item) => item.id === character.id);
                const thumbnail = libraryMatch?.thumbnail_path
                  ? `/api/v1/studio/characters/${character.id}/thumbnail`
                  : null;
                const voice = voices.find((profile) => profile.voice_id === character.voice_id);
                const isReferenced = scenes.some(
                  (scene) =>
                    scene.character_placements.some(
                      (placement) => placement.character_id === character.id
                    ) || scene.dialogues.some((dialogue) => dialogue.character_id === character.id)
                );

                return (
                  <article
                    key={character.id}
                    className="rounded-xl border border-slate-200 bg-white p-3 dark:border-white/[0.08] dark:bg-white/[0.02]"
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-xl text-sm font-extrabold text-white"
                        style={{
                          background:
                            character.style.shirt_color ||
                            libraryMatch?.palette.shirt_color ||
                            '#7367F0',
                        }}
                      >
                        {thumbnail ? (
                          <img
                            src={thumbnail}
                            alt=""
                            className="h-full w-full object-cover"
                            onError={(event) => {
                              (event.target as HTMLImageElement).style.display = 'none';
                            }}
                          />
                        ) : (
                          character.name.slice(0, 1).toLocaleUpperCase('tr-TR')
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <h4 className="truncate text-xs font-bold text-slate-800 dark:text-white">
                              {character.name}
                            </h4>
                            <p className="mt-0.5 line-clamp-2 text-[10px] leading-relaxed text-slate-500 dark:text-slate-400">
                              {libraryMatch?.description || 'Proje karakteri'}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-0.5">
                            <button
                              type="button"
                              onClick={() => openEdit(character)}
                              aria-label={`${character.name} karakterini düzenle`}
                              title="Karakteri düzenle"
                              className="rounded p-1 text-slate-300 transition hover:bg-[#7367F0]/10 hover:text-[#7367F0]"
                            >
                              <Edit2 className="h-3.5 w-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => removeCharacter(character.id)}
                              disabled={isSaving || isReferenced || cast.length <= 1}
                              title={
                                isReferenced
                                  ? 'Sahnelerde kullanılan karakter çıkarılamaz'
                                  : cast.length <= 1
                                  ? 'En az bir karakter gerekli'
                                  : 'Kadrodan çıkar'
                              }
                              className="rounded p-1 text-slate-300 transition hover:bg-red-50 hover:text-red-500 disabled:cursor-not-allowed disabled:opacity-40 dark:hover:bg-red-950/30"
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                        <div className="mt-2 flex items-center gap-1">
                          {[
                            character.style.hair_color,
                            character.style.skin_tone,
                            character.style.shirt_color,
                            character.style.pants_color,
                          ].map((color, index) => (
                            <span
                              key={`${color}-${index}`}
                              className="h-3 w-3 rounded-full border border-white/70 shadow-sm"
                              style={{ backgroundColor: color }}
                            />
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="mt-3">
                      <label className="mb-1 block text-[10px] font-bold text-slate-500 dark:text-slate-400">
                        Ses profili
                      </label>
                      <select
                        value={character.voice_id}
                        onChange={(event) => updateVoice(character.id, event.target.value)}
                        disabled={isSaving}
                        className="vuexy-input h-8 w-full px-2 text-[11px]"
                      >
                        {voices.length === 0 && <option value={character.voice_id}>Varsayılan</option>}
                        {character.voice_id && !voice && (
                          <option value={character.voice_id}>{character.voice_id} (katalog dışı)</option>
                        )}
                        {voices.map((profile) => (
                          <option key={profile.voice_id} value={profile.voice_id}>
                            {profile.name} · {profile.language}
                          </option>
                        ))}
                      </select>
                      {voice?.preview_url ? (
                        <audio
                          controls
                          preload="none"
                          src={voice.preview_url}
                          className="mt-1.5 h-8 w-full"
                        />
                      ) : (
                        <p className="mt-1 text-[9px] text-slate-400">
                          {voice
                            ? 'Bu profil için resmi önizleme URL’si yok.'
                            : 'Ses profili eşleşmedi.'}
                        </p>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-[#7367F0]" />
                Kütüphaneden ekle
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {availableCharacters.length === 0 ? (
                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                  Kütüphanedeki tüm karakterler proje kadrosunda.
                </p>
              ) : (
                availableCharacters.slice(0, 8).map((character) => (
                  <div
                    key={character.id}
                    className="flex items-center gap-2 rounded-lg border border-slate-200 p-2 dark:border-white/[0.08]"
                  >
                    <div
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold text-white"
                      style={{ backgroundColor: character.palette.shirt_color }}
                    >
                      {character.name.slice(0, 1).toLocaleUpperCase('tr-TR')}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[11px] font-bold text-slate-700 dark:text-slate-200">
                        {character.name}
                      </div>
                      <div className="truncate text-[9px] text-slate-400">
                        {character.gender} · {character.voice_id || 'ses atanmadı'}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => addCharacter(character)}
                      disabled={isSaving}
                      aria-label={`${character.name} karakterini projeye ekle`}
                      className="rounded-lg p-1.5 text-[#7367F0] transition hover:bg-[#7367F0]/10 disabled:opacity-40"
                    >
                      <Plus className="h-4 w-4" />
                    </button>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2">
                <Volume2 className="h-4 w-4 text-[#7367F0]" />
                Konuşmacı sesleri
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {voices.slice(0, 4).map((voice) => (
                <div key={voice.voice_id} className="rounded-lg bg-slate-50 p-2 dark:bg-white/[0.03]">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[10px] font-bold text-slate-700 dark:text-slate-200">
                      {voice.name}
                    </span>
                    <span className="shrink-0 text-[9px] text-slate-400">{voice.gender}</span>
                  </div>
                  {voice.preview_url && (
                    <audio controls preload="none" src={voice.preview_url} className="mt-1 h-7 w-full" />
                  )}
                </div>
              ))}
              {voices.length === 0 && (
                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                  Ses kataloğu yüklenemedi.
                </p>
              )}
            </CardContent>
          </Card>

          <Button variant="outline" size="md" onClick={onNext} className="w-full gap-2">
            Sahneler adımına geç
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <Modal
        isOpen={isEditOpen}
        onClose={() => {
          setIsEditOpen(false);
          setEditingCharacter(null);
        }}
        title="Karakteri Düzenle"
        maxWidth="lg"
      >
        <form onSubmit={saveCharacterEdit} className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
              Karakter adı
              <input
                value={editForm.name}
                onChange={(event) =>
                  setEditForm((previous) => ({ ...previous, name: event.target.value }))
                }
                maxLength={80}
                autoFocus
                className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal"
              />
            </label>
            <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
              Ses profili
              <select
                value={editForm.voice_id}
                onChange={(event) =>
                  setEditForm((previous) => ({ ...previous, voice_id: event.target.value }))
                }
                className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal"
              >
                {editForm.voice_id && !voices.some((voice) => voice.voice_id === editForm.voice_id) && (
                  <option value={editForm.voice_id}>{editForm.voice_id} (katalog dışı)</option>
                )}
                {voices.map((voice) => (
                  <option key={voice.voice_id} value={voice.voice_id}>
                    {voice.name} · {voice.language}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="rounded-xl border border-slate-200 p-3 dark:border-white/[0.08]">
            <div className="mb-2 text-[11px] font-bold text-slate-600 dark:text-slate-300">
              Görünüm renkleri
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {(
                [
                  ['hair_color', 'Saç'],
                  ['skin_tone', 'Ten'],
                  ['shirt_color', 'Üst'],
                  ['pants_color', 'Alt'],
                ] as Array<[keyof typeof editForm, string]>
              ).map(([key, label]) => (
                <label key={key} className="text-[10px] font-semibold text-slate-500">
                  {label}
                  <span className="mt-1 flex items-center gap-1.5">
                    <input
                      type="color"
                      value={editForm[key]}
                      onChange={(event) =>
                        setEditForm((previous) => ({ ...previous, [key]: event.target.value }))
                      }
                      aria-label={`${label} rengi`}
                      className="h-8 w-9 cursor-pointer rounded border border-slate-200 bg-white dark:border-white/[0.12]"
                    />
                    <span className="font-mono text-[9px] text-slate-400">{editForm[key]}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>

          {error && <StudioAlert tone="error">{error}</StudioAlert>}
          <div className="flex flex-col-reverse gap-2 pt-1 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              size="md"
              onClick={() => {
                setIsEditOpen(false);
                setEditingCharacter(null);
              }}
              disabled={isUpdatingCharacter}
            >
              Vazgeç
            </Button>
            <Button
              type="submit"
              size="md"
              disabled={isUpdatingCharacter || !editForm.name.trim()}
              className="gap-2"
            >
              {isUpdatingCharacter ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Edit2 className="h-4 w-4" />
              )}
              Karakteri kaydet
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Yeni Karakter"
        maxWidth="lg"
      >
        <form onSubmit={createAndAdd} className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
              Karakter adı
              <input
                value={newCharacter.name}
                onChange={(event) => setNewCharacter((prev) => ({ ...prev, name: event.target.value }))}
                maxLength={80}
                autoFocus
                className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal"
              />
            </label>
            <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
              Cinsiyet
              <select
                value={newCharacter.gender}
                onChange={(event) =>
                  setNewCharacter((prev) => ({ ...prev, gender: event.target.value as Character['gender'] }))
                }
                className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal"
              >
                <option value="neutral">Nötr</option>
                <option value="female">Kadın</option>
                <option value="male">Erkek</option>
              </select>
            </label>
          </div>
          <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-300">
            Açıklama
            <textarea
              value={newCharacter.description}
              onChange={(event) =>
                setNewCharacter((prev) => ({ ...prev, description: event.target.value }))
              }
              rows={3}
              className="vuexy-input mt-1 w-full resize-y px-2 py-1.5 text-xs font-normal"
            />
          </label>
          <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-300">
            Ses profili
            <select
              value={newCharacter.voice_id}
              onChange={(event) =>
                setNewCharacter((prev) => ({ ...prev, voice_id: event.target.value }))
              }
              className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal"
            >
              {voices.map((voice) => (
                <option key={voice.voice_id} value={voice.voice_id}>
                  {voice.name} · {voice.language}
                </option>
              ))}
            </select>
          </label>
          {!voiceStatus?.is_configured && (
            <StudioAlert tone="warning">
              ElevenLabs yapılandırılmadığı için bu ses profili yalnızca atama bilgisi olarak
              saklanır; render sırasında yeni ses üretilemez.
            </StudioAlert>
          )}
          <div className="flex flex-col-reverse gap-2 pt-1 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              size="md"
              onClick={() => setIsCreateOpen(false)}
              disabled={isCreating}
            >
              Vazgeç
            </Button>
            <Button type="submit" size="md" disabled={isCreating || !newCharacter.name.trim()} className="gap-2">
              {isCreating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              Karakteri oluştur ve ekle
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
