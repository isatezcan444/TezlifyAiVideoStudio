import React, { useState } from 'react';
import {
  ArrowRight,
  CheckCircle2,
  Clapperboard,
  Loader2,
  RefreshCw,
  Sparkles,
  Users,
} from 'lucide-react';
import { SceneGraph, StudioProject } from '../../../types/studio';
import { apiService } from '../../../services/api';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { StudioAlert, StudioSectionTitle } from '../StudioShared';

interface StoryStepProps {
  project: StudioProject;
  onSaveSceneGraph: (sceneGraph: SceneGraph) => Promise<StudioProject>;
  onNext: () => void;
}

const EXAMPLE_PROMPTS = [
  'Ali ve Ayşe bir kafede buluşur; samimi, sıcak ve kısa bir Türkçe hikâye.',
  'Bir karakter sabah rutinini anlatırken küçük bir sürprizle karşılaşır.',
  'İki arkadaş şehirde kısa bir yürüyüş yaparken gelecek planlarını konuşur.',
];

export const StoryStep: React.FC<StoryStepProps> = ({
  project,
  onSaveSceneGraph,
  onNext,
}) => {
  const [prompt, setPrompt] = useState(
    project.description || 'Ali ve Ayşe bir kafede buluşur; samimi ve sıcak bir Türkçe hikâye.'
  );
  const [targetDuration, setTargetDuration] = useState(15);
  const [aspectRatio, setAspectRatio] = useState<'16:9' | '9:16' | '1:1'>(
    project.scene_graph?.resolution.aspect_ratio || '16:9'
  );
  const [genre, setGenre] = useState('');
  const [provider, setProvider] = useState<'auto' | 'template' | 'ollama'>('auto');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const scenes = project.scene_graph?.scenes || [];
  const characters = project.scene_graph?.characters || [];
  const hasStory = scenes.length > 0;

  const generate = async () => {
    if (!prompt.trim()) {
      setError('Hikâye istemi boş olamaz.');
      return;
    }
    setIsGenerating(true);
    setError(null);
    setMessage(null);
    try {
      const response = await apiService.generateStory({
        prompt: prompt.trim(),
        target_duration_seconds: targetDuration,
        aspect_ratio: aspectRatio,
        genre: genre.trim() || undefined,
        provider,
      });
      await onSaveSceneGraph(response.scene_graph);
      setMessage(
        `Senaryo hazır: ${response.scene_count} sahne, ${response.character_count} karakter. Yeni SceneGraph kaydedildi.`
      );
    } catch (err: any) {
      setError(err.message || 'Hikâye üretilemedi.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-5">
      <StudioSectionTitle
        title="Hikâye ve senaryo"
        description="Mevcut Story Director altyapısıyla yeni bir SceneGraph üretin veya var olan sahnelerle devam edin."
        action={
          hasStory ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
              <CheckCircle2 className="h-3 w-3" />
              Hikâye hazır
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[10px] font-bold text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
              <RefreshCw className="h-3 w-3" />
              Hikâye bekliyor
            </span>
          )
        }
      />

      {error && <StudioAlert tone="error">{error}</StudioAlert>}
      {message && <StudioAlert tone="success">{message}</StudioAlert>}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-[#7367F0]" />
              Hikâye üret
            </CardTitle>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Türkçe senaryo promptu, süre ve format bilgisiyle sahne grafiği oluşturulur.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label htmlFor="story-prompt" className="mb-1.5 block text-xs font-bold text-slate-700 dark:text-slate-200">
                Hikâye istemi
              </label>
              <textarea
                id="story-prompt"
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                rows={5}
                maxLength={2000}
                className="vuexy-input w-full resize-y px-3 py-2 text-sm"
              />
              <div className="mt-2 flex flex-wrap gap-1.5">
                {EXAMPLE_PROMPTS.map((example, index) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => setPrompt(example)}
                    className="rounded-lg bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-500 transition hover:bg-[#7367F0]/10 hover:text-[#7367F0] dark:bg-white/[0.06] dark:text-slate-300"
                  >
                    Örnek {index + 1}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
                Hedef süre
                <input
                  type="number"
                  min={5}
                  max={180}
                  value={targetDuration}
                  onChange={(event) => setTargetDuration(Number(event.target.value))}
                  className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal"
                />
              </label>
              <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
                Format
                <select
                  value={aspectRatio}
                  onChange={(event) => setAspectRatio(event.target.value as '16:9' | '9:16' | '1:1')}
                  className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal"
                >
                  <option value="16:9">16:9</option>
                  <option value="9:16">9:16</option>
                  <option value="1:1">1:1</option>
                </select>
              </label>
              <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
                Tür
                <input
                  type="text"
                  value={genre}
                  onChange={(event) => setGenre(event.target.value)}
                  placeholder="dram, komedi..."
                  className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal"
                />
              </label>
              <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
                Sağlayıcı
                <select
                  value={provider}
                  onChange={(event) => setProvider(event.target.value as 'auto' | 'template' | 'ollama')}
                  className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal"
                >
                  <option value="auto">Otomatik</option>
                  <option value="template">Şablon</option>
                  <option value="ollama">Ollama</option>
                </select>
              </label>
            </div>

            <StudioAlert tone="warning">
              Yeni hikâye üretimi mevcut SceneGraph’i değiştirir. Daha önce yaptığınız sahne
              düzenlemeleri korunmaz; önce mevcut hikâyeyle ilerlemek istiyorsanız bu adımı atlayın.
            </StudioAlert>

            <Button onClick={generate} disabled={isGenerating} size="md" className="w-full gap-2">
              {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {isGenerating ? 'Senaryo üretiliyor...' : hasStory ? 'Yeni hikâye üret' : 'Hikâye üret'}
            </Button>
          </CardContent>
        </Card>

        <div className="space-y-4 xl:col-span-2">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2">
                <Clapperboard className="h-4 w-4 text-[#7367F0]" />
                Mevcut hikâye
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-2 text-center">
                <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-white/[0.03]">
                  <div className="text-lg font-extrabold text-slate-800 dark:text-white">{scenes.length}</div>
                  <div className="text-[10px] font-semibold text-slate-400">sahne</div>
                </div>
                <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-white/[0.03]">
                  <div className="text-lg font-extrabold text-slate-800 dark:text-white">{characters.length}</div>
                  <div className="text-[10px] font-semibold text-slate-400">karakter</div>
                </div>
              </div>
              {scenes.length === 0 ? (
                <p className="rounded-xl border border-dashed border-slate-200 p-4 text-center text-xs text-slate-400 dark:border-white/[0.1]">
                  Henüz sahne yok.
                </p>
              ) : (
                <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                  {scenes.map((scene, index) => (
                    <div key={scene.scene_id} className="rounded-lg border border-slate-200 p-2.5 dark:border-white/[0.08]">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-bold text-slate-700 dark:text-slate-200">
                          {index + 1}. {scene.scene_id}
                        </span>
                        <span className="text-[10px] text-slate-400">{scene.duration_seconds.toFixed(1)} sn</span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-[11px] text-slate-500 dark:text-slate-400">
                        {scene.dialogues.map((dialogue) => dialogue.text).join(' · ') || 'Diyalog yok'}
                      </p>
                    </div>
                  ))}
                </div>
              )}
              {characters.length > 0 && (
                <div className="flex items-center gap-2 border-t border-slate-100 pt-3 text-[11px] text-slate-500 dark:border-white/[0.06] dark:text-slate-400">
                  <Users className="h-3.5 w-3.5 text-[#7367F0]" />
                  <span className="truncate">{characters.map((character) => character.name).join(', ')}</span>
                </div>
              )}
            </CardContent>
          </Card>
          <Button variant="outline" size="md" onClick={onNext} className="w-full gap-2">
            Karakterler adımına geç
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};
