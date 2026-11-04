import React, { useState } from 'react';
import {
  AlertCircle,
  Edit2,
  ExternalLink,
  Loader2,
  Mic,
  Plus,
  UserPlus,
  Users,
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
import { Card, CardContent } from '../../ui/card';
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
}

function styleFromCharacter(character: Character): SceneGraphCharacter['style'] {
  return {
    hair_color: character.palette.hair_color,
    skin_tone: character.palette.skin_tone,
    shirt_color: character.palette.shirt_color,
    pants_color: character.palette.pants_color,
  };
}

function proportionsFromBodyType(body_type: 'slim' | 'average' | 'athletic') {
  const presets = {
    slim: { head_scale: 0.90, torso_length: 0.95, arm_length: 0.90, leg_length: 0.95, shoulder_width: 0.90 },
    average: { head_scale: 1.00, torso_length: 1.00, arm_length: 1.00, leg_length: 1.00, shoulder_width: 1.00 },
    athletic: { head_scale: 1.00, torso_length: 1.05, arm_length: 1.05, leg_length: 1.00, shoulder_width: 1.10 },
  };
  return presets[body_type];
}

function bodyTypeFromProportions(proportions: { head_scale: number; torso_length: number; arm_length: number; leg_length: number; shoulder_width: number } | undefined): 'slim' | 'average' | 'athletic' {
  if (!proportions) return 'average';
  const presets: Record<'slim' | 'average' | 'athletic', { head_scale: number; torso_length: number; arm_length: number; leg_length: number; shoulder_width: number }> = {
    slim: { head_scale: 0.90, torso_length: 0.95, arm_length: 0.90, leg_length: 0.95, shoulder_width: 0.90 },
    average: { head_scale: 1.00, torso_length: 1.00, arm_length: 1.00, leg_length: 1.00, shoulder_width: 1.00 },
    athletic: { head_scale: 1.00, torso_length: 1.05, arm_length: 1.05, leg_length: 1.00, shoulder_width: 1.10 },
  };
  for (const [type, preset] of Object.entries(presets)) {
    const t = type as 'slim' | 'average' | 'athletic';
    const p = preset as { head_scale: number; torso_length: number; arm_length: number; leg_length: number; shoulder_width: number };
    if (
      Math.abs(proportions.head_scale - p.head_scale) < 0.01 &&
      Math.abs(proportions.torso_length - p.torso_length) < 0.01 &&
      Math.abs(proportions.arm_length - p.arm_length) < 0.01 &&
      Math.abs(proportions.leg_length - p.leg_length) < 0.01 &&
      Math.abs(proportions.shoulder_width - p.shoulder_width) < 0.01
    ) {
      return t;
    }
  }
  return 'average';
}

const CLOTHING_STYLE_OPTIONS: Array<[string, string]> = [
  ['casual', 'Günlük'],
  ['formal', 'Resmi'],
  ['hoodie', 'Kapüşonlu'],
  ['sporty', 'Spor'],
];

const EYE_STYLE_OPTIONS = [
  ['dot', 'Nokta'],
  ['round', 'Yuvarlak'],
  ['anime', 'Anime'],
  ['minimal', 'Minimal'],
] as const;

const BODY_TYPE_OPTIONS = [
  ['slim', 'Ince'],
  ['average', 'Orta'],
  ['athletic', 'Atletik'],
] as const;

export const CharactersStep: React.FC<CharactersStepProps> = ({
  project,
  library,
  voices,
  voiceStatus,
  onSaveSceneGraph,
  onCreateCharacter,
  onUpdateCharacter,
  onOpenCharacterStudio,
}) => {
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
    clothing_style: 'casual',
    eye_style: 'round',
    body_type: 'average',
  });
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [newCharacter, setNewCharacter] = useState({
    name: '',
    description: '',
    gender: 'neutral',
    voice_id: voices[0]?.voice_id || '',
    clothing_style: 'casual',
    eye_style: 'round',
    body_type: 'average',
  });

  const sceneGraph = project.scene_graph;
  const cast = sceneGraph?.characters || [];
  const scenes = sceneGraph?.scenes || [];
  const castIds = new Set(cast.map((character) => character.id));
  const availableCharacters = library.filter((character) => !castIds.has(character.id));

  const saveGraph = async (nextGraph: SceneGraph, successMessage: string) => {
    setError(null);
    setMessage(null);
    try {
      await onSaveSceneGraph(nextGraph);
      setMessage(successMessage);
    } catch (err: any) {
      setError(err.message || 'Karakter değişiklikleri kaydedilemedi.');
      throw err;
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
        gender: newCharacter.gender as 'male' | 'female' | 'neutral',
        voice_id: newCharacter.voice_id,
        clothing_style: newCharacter.clothing_style,
        eye_style: newCharacter.eye_style,
        proportions: proportionsFromBodyType(newCharacter.body_type as 'slim' | 'average' | 'athletic'),
      });
      await addCharacter(created);
      setIsCreateOpen(false);
      setNewCharacter({
        name: '',
        description: '',
        gender: 'neutral',
        voice_id: voices[0]?.voice_id || '',
        clothing_style: 'casual',
        eye_style: 'round',
        body_type: 'average',
      });
    } catch (err: any) {
      setError(err.message || 'Karakter oluşturulamadı.');
    } finally {
      setIsCreating(false);
    }
  };

  const openEdit = (character: SceneGraphCharacter) => {
    setEditingCharacter(character);
    const libraryMatch = library.find((item) => item.id === character.id);
    setEditForm({
      name: character.name,
      voice_id: character.voice_id,
      hair_color: character.style.hair_color,
      skin_tone: character.style.skin_tone,
      shirt_color: character.style.shirt_color,
      pants_color: character.style.pants_color,
      clothing_style: libraryMatch?.clothing_style || 'casual',
      eye_style: libraryMatch?.eye_style || 'round',
      body_type: bodyTypeFromProportions(libraryMatch?.proportions),
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
        const proportions = proportionsFromBodyType(editForm.body_type as 'slim' | 'average' | 'athletic');
        await onUpdateCharacter(editingCharacter.id, {
          name: editForm.name.trim(),
          voice_id: editForm.voice_id,
          clothing_style: editForm.clothing_style,
          eye_style: editForm.eye_style,
          palette: {
            ...palette,
            hair_color: editForm.hair_color,
            skin_tone: editForm.skin_tone,
            shirt_color: editForm.shirt_color,
            pants_color: editForm.pants_color,
          },
          proportions,
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

  // Pre-compute character cards to avoid complex nested JSX
  const characterCards = cast.map((character) => {
    const libraryMatch = library.find((item) => item.id === character.id);
    return (
      <article key={character.id} className="rounded-xl border border-slate-200 p-3 dark:border-white/[0.08] dark:bg-white/[0.02]">
        <div className="flex items-start gap-3">
          <div className="flex h-12 w-9 shrink-0 items-center justify-center rounded-xl text-xs font-extrabold text-white" style={{ backgroundColor: character.style.shirt_color || libraryMatch?.palette?.shirt_color || '#7367F0' }}>
            {character.name.slice(0, 1).toLocaleUpperCase('tr-TR')}
          </div>
          <div className="flex-1">
            <div className="flex items-start gap-2">
              <div className="min-w-0">
                <h4 className="truncate text-xs font-bold text-slate-700 dark:text-slate-200">
                  {character.name}
                </h4>
                <p className="mt-0.5 line-clamp-2 text-[10px] leading-relaxed text-slate-500 dark:text-slate-400">
                  {libraryMatch?.description || 'Proje karakteri'}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <button
                  type="button"
                  onClick={() => openEdit(character)}
                  aria-label={`${character.name} karakterini düzenle`}
                  className="rounded p-1 text-slate-300 transition hover:bg-[#7367F0]/10 hover:text-[#7367F0]"
                >
                  <Edit2 className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => removeCharacter(character.id)}
                  className="rounded p-1 text-slate-300 dark:text-slate-400 hover:bg-red-50 dark:hover:bg-red-950/30 dark:text-red-400 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            </div>
            <div className="mt-2 flex items-center gap-2">
              {[character.style.hair_color, character.style.skin_tone, character.style.shirt_color, character.style.pants_color].map((color, index) => (
                <div key={`${color}-${index}`} className="h-3 w-3 rounded-md rounded-sm" style={{ backgroundColor: color }} />
              ))}
            </div>
            <div className="mt-3">
              <label className="mb-1 block text-[10px] font-bold text-slate-500 dark:text-slate-400">
                Ses profili
              </label>
              <select
                value={character.voice_id}
                onChange={(event) => updateVoice(character.id, event.target.value)}
                disabled={isUpdatingCharacter}
                className="vuexy-input h-8 w-full px-2 text-[11px]"
              >
                {voices.length === 0 && <option value={character.voice_id}>Varsayılan</option>}
                {voices.map((profile) => (
                  <option key={profile.voice_id} value={profile.voice_id}>
                    {profile.name} · {profile.language}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="mt-2 flex items-center gap-2">
            <Button size="md" variant="outline" onClick={() => openEdit(character)} className="flex-1 gap-2" disabled={isUpdatingCharacter}>
              <Edit2 className="h-3 w-3" />
              Düzenle
            </Button>
            <Button type="button" variant="outline" size="md" onClick={() => removeCharacter(character.id)} className="flex-1 text-red-500 dark:text-red-500">
              <X className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </article>
    );
  });

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
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-slate-800 dark:text-white">
                <Mic className="h-4 w-4" />
              </div>
              <div>
                <div className="text-xs font-bold text-slate-700 dark:text-slate-200">
                  Ses kaynağı: {voiceStatus?.is_configured ? 'ElevenLabs bağlı' : 'ElevenLabs bağlantısı yok'}
                </div>
                <p className="mt-0.5 text-[10px] text-slate-500 dark:text-slate-400">
                  {voiceStatus?.is_configured ? `Model: ${voiceStatus?.default_model || 'global'} · ${voices.length} ses profili kullanılabilir.` : 'ElevenLabs yapılandırılmadı'}
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

      <div className="flex flex-col gap-5 sm:flex-row">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-sm font-bold text-slate-700 dark:text-slate-200">
              <Users className="h-4 w-4 text-[#7367F0]" />
              Karakter Kadrosu
            </h3>
          </div>

          <div className="rounded-xl border border-slate-200 p-4 dark:border-white/[0.08] dark:bg-white/[0.02]">
            <div className="flex items-center gap-2 mb-2">
              <h4 className="text-sm font-bold text-slate-700 dark:text-slate-200">Proje kadrosu</h4>
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between text-[10px] font-bold text-slate-500 dark:text-slate-400">
                <span>{cast.length} karakter</span>
              </div>
            </div>

            {cast.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-xs text-slate-400 dark:border-white/[0.08] dark:bg-white/[0.02]">
                Proje kadrosu boş. Karakter ekleyin.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                {characterCards}
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2 pt-1">
            {availableCharacters.map((character) => (
              <div key={character.id} className="flex items-center gap-2">
                <div className="flex-1">
                  <span className="text-[11px] font-bold text-slate-600 dark:text-slate-200 truncate">{character.name}</span>
                  <div className="flex items-center gap-2 text-[10px] text-slate-500 dark:text-slate-300">
                    {character.hair_style} &bull; {character.gender}
                  </div>
                </div>
                <Button size="md" onClick={() => addCharacter(character)} className="flex-1 gap-2">
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
        </div>

        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-sm font-bold text-slate-700 dark:text-slate-200">
              <Users className="h-4 w-4 text-[#7367F0]" />
              Kütüphaneden Ekle
            </h3>
          </div>

          <div className="rounded-xl border border-slate-200 p-4 dark:border-white/[0.08] dark:bg-white/[0.02]">
            <div className="flex flex-col gap-3">
              {availableCharacters.length === 0 ? (
                <p className="text-[11px] text-slate-500 dark:text-slate-400 text-center py-4">
                  Kütüphanedeki tüm karakterler proje kadrosunda.
                </p>
              ) : (
                availableCharacters.map((character) => (
                  <div key={character.id} className="rounded-lg border border-slate-200 p-3 dark:border-white/[0.08] dark:bg-white/[0.02]">
                    <div className="flex items-center gap-2">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/[0.3] dark:bg-white/[0.05] text-[11px] font-bold text-slate-700 dark:text-slate-200">
                        {character.name.slice(0, 1).toLocaleUpperCase('tr-TR')}
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className="truncate text-[11px] font-bold text-slate-700 dark:text-slate-200">{character.name}</span>
                        <div className="flex items-center gap-2 text-[10px] text-slate-500 dark:text-slate-300 mt-1">
                          {character.hair_style} &bull; {character.gender}
                        </div>
                      </div>
                      <Button size="md" onClick={() => addCharacter(character)} className="flex-1 gap-2">
                        <Plus className="h-3 w-3" />
                        Ekle
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      <Modal isOpen={isEditOpen} onClose={() => setIsEditOpen(false)} title="Karakter Düzenle" maxWidth="lg">
        <form onSubmit={saveCharacterEdit} className="space-y-4">
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
                Karakter adı
                <input
                  value={editForm.name}
                  onChange={(event) => setEditForm((previous) => ({ ...previous, name: event.target.value }))}
                  maxLength={80}
                  autoFocus
                  className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal"
                />
              </label>
              <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
                Ses profili
                <select
                  value={editForm.voice_id}
                  onChange={(event) => setEditForm((previous) => ({ ...previous, voice_id: event.target.value }))}
                  className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal"
                >
                  {voices.map((voice) => (
                    <option key={voice.voice_id} value={voice.voice_id}>
                      {voice.name} · {voice.language}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
                Giysi tarzı
                <select
                  value={editForm.clothing_style}
                  onChange={(event) => setEditForm((previous) => ({ ...previous, clothing_style: event.target.value as Character['clothing_style'] }))}
                  className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal"
                >
                  {CLOTHING_STYLE_OPTIONS.map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
              <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
                Göz tarzı
                <select
                  value={editForm.eye_style}
                  onChange={(event) => setEditForm((previous) => ({ ...previous, eye_style: event.target.value as Character['eye_style'] }))}
                  className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal"
                >
                  {EYE_STYLE_OPTIONS.map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
              <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
                Vücut tipi
                <select
                  value={editForm.body_type}
                  onChange={(event) =>
                    setEditForm((previous) => ({ ...previous, body_type: event.target.value as 'slim' | 'average' | 'athletic' }))
                  }
                  className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal"
                >
                  {BODY_TYPE_OPTIONS.map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="mt-2 text-[11px] font-bold text-slate-600 dark:text-slate-300">
              Görünüm renkleri
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                ['hair_color', 'Saç'],
                ['skin_tone', 'Ten'],
                ['shirt_color', 'Üst'],
                ['pants_color', 'Alt'],
              ].map(([key, label]) => {
                const formValue = (editForm as Record<string, string>)[key];
                return (
                  <label key={key} className="text-[10px] font-semibold text-slate-500 dark:text-slate-300 flex flex-col gap-1 p-2 rounded-xl border border-slate-200 bg-white dark:border-white/[0.08]">
                    {label}
                    <span className="mt-1 flex items-center gap-1.5">
                      <input
                        type="color"
                        value={formValue}
                        onChange={(event) => setEditForm((previous) => ({ ...previous, [key]: event.target.value }))}
                        aria-label={`${label} rengi`}
                        className="h-8 w-9 cursor-pointer rounded border border-slate-200 bg-white dark:border-white/[0.08]"
                      />
                      <span className="font-mono text-[9px] text-slate-400">{formValue}</span>
                    </span>
                  </label>
                );
              })}
            </div>
            <div className="flex flex-col-reverse gap-2 pt-1 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" size="md" onClick={() => setIsEditOpen(false)} disabled={isUpdatingCharacter}>
                Vazgeç
              </Button>
              <Button type="submit" size="md" disabled={isUpdatingCharacter || !editForm.name.trim()} className="gap-2">
                {isUpdatingCharacter ? <Loader2 className="h-4 w-4 animate-spin" /> : <Edit2 className="h-4 w-4" />}
                Karakteri kaydet
              </Button>
            </div>
          </div>
        </form>
      </Modal>

      <Modal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} title="Yeni Karakter" maxWidth="lg">
        <form onSubmit={createAndAdd} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
              Karakter adı
              <input value={newCharacter.name} onChange={(event) => setNewCharacter((prev) => ({ ...prev, name: event.target.value }))} className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal" />
            </label>
            <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
              Açıklama
              <textarea value={newCharacter.description} onChange={(event) => setNewCharacter((prev) => ({ ...prev, description: event.target.value }))} rows={3} className="vuexy-input mt-1 w-full resize-y px-2 py-1.5 text-xs font-normal" />
            </label>
            <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
              Ses profili
              <select value={newCharacter.voice_id} onChange={(event) => setNewCharacter((prev) => ({ ...prev, voice_id: event.target.value }))} className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal">
                {voices.map((voice) => (
                  <option key={voice.voice_id} value={voice.voice_id}>
                    {voice.name} · {voice.language}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
              Giysi tarzı
              <select value={newCharacter.clothing_style} onChange={(event) => setNewCharacter((prev) => ({ ...prev, clothing_style: event.target.value as Character['clothing_style'] }))} className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal">
                {CLOTHING_STYLE_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
              Göz tarzı
              <select value={newCharacter.eye_style} onChange={(event) => setNewCharacter((prev) => ({ ...prev, eye_style: event.target.value as Character['eye_style'] }))} className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal">
                {EYE_STYLE_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
              Vücut tipi
              <select value={newCharacter.body_type} onChange={(event) => setNewCharacter((prev) => ({ ...prev, body_type: event.target.value as 'slim' | 'average' | 'athletic' }))} className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal">
                {BODY_TYPE_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            {!voiceStatus?.is_configured && (
              <StudioAlert tone="warning">
                ElevenLabs yapılandırılmadığı için bu ses profili yalnızca proje kadrosunda gösterilir. Gerçek ses üretimi için ElevenLabs bağlantısı gerekir.
              </StudioAlert>
            )}
            <div className="flex flex-col-reverse gap-2 pt-1 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" size="md" onClick={() => setIsCreateOpen(false)} disabled={isCreating}>
                Vazgeç
              </Button>
              <Button type="submit" size="md" disabled={isCreating || !newCharacter.name.trim()} className="gap-2">
                {isCreating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                Karakteri kaydet
              </Button>
            </div>
          </div>
        </form>
      </Modal>
    </div>
  );
};