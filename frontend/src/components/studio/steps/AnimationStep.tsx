import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Film,
  Loader2,
  Play,
  RefreshCw,
  Volume2,
} from 'lucide-react';
import {
  RenderJob,
  SceneGraphScene,
  StudioProject,
  VoiceStatusResponse,
} from '../../../types/studio';
import { apiService } from '../../../services/api';
import {
  isAnimationRender,
  isLiveRender,
  isStalePending,
  latestRenderForProject,
} from '../../../lib/studioWorkspace';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import {
  formatRenderDuration,
  RenderStatusPanel,
  StudioAlert,
  StudioSectionTitle,
} from '../StudioShared';

interface AnimationStepProps {
  project: StudioProject;
  renders: RenderJob[];
  voiceStatus: VoiceStatusResponse | null;
  onRefresh: () => Promise<void>;
  onNext: () => void;
}

/**
 * Pre-render checks are derived from the scene graph the renderer will actually
 * receive, so this list can only ever show problems the worker would also hit.
 */
function sceneChecks(scene: SceneGraphScene): Array<{ ok: boolean; label: string }> {
  const lines = scene.dialogues || [];
  const missingAudio = lines.filter((line) => !line.audio_file).length;
  const missingVisemes = lines.filter((line) => !(line.visemes && line.visemes.length)).length;
  return [
    { ok: lines.length > 0, label: lines.length ? `${lines.length} replik` : 'replik yok' },
    {
      ok: lines.length > 0 && missingAudio === 0,
      label: lines.length === 0 ? 'ses yok' : missingAudio ? `${missingAudio} repliğin sesi yok` : 'ses hazır',
    },
    {
      ok: lines.length > 0 && missingVisemes === 0,
      label: lines.length === 0
        ? 'viseme yok'
        : missingVisemes
          ? `${missingVisemes} replik ölçülmemiş (ağız tahmini)`
          : 'ölçülmüş viseme',
    },
    { ok: scene.character_placements.length >= 2, label: `${scene.character_placements.length} karakter` },
  ];
}

function ScenePlanCard({ scene, index, names, metadata }: {
  scene: SceneGraphScene;
  index: number;
  names: Record<string, string>;
  metadata: RenderJob['output_metadata'];
}) {
  const checks = sceneChecks(scene);
  const speakerLines = scene.dialogues.map((line) => ({
    speaker: names[line.character_id] || line.character_id,
    listener: scene.character_placements
      .map((placement) => placement.character_id)
      .filter((id) => id !== line.character_id)
      .map((id) => names[id] || id)
      .join(', '),
    text: line.text,
    range: `${line.start_time.toFixed(1)}–${line.end_time.toFixed(1)}s`,
  }));
  const animated = (metadata?.animation?.scenes || []).filter(
    (entry) => entry.scene_id === scene.scene_id
  );
  const lipModes = (metadata?.lip_sync?.scenes || [])
    .filter((entry) => entry.scene_id === scene.scene_id)
    .flatMap((entry) => Object.entries(entry.speakers || {}));

  return (
    <div className="rounded-xl border border-slate-200 p-3 dark:border-white/[0.08]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs font-bold text-slate-700 dark:text-slate-200">
          Sahne {index + 1} · <span className="font-mono text-[10px] text-slate-400">{scene.scene_id}</span>
        </div>
        <div className="flex flex-wrap items-center gap-1 text-[10px] text-slate-500 dark:text-slate-400">
          <span className="rounded-full bg-slate-100 px-2 py-0.5 dark:bg-white/[0.06]">
            {scene.duration_seconds.toFixed(1)}s
          </span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 dark:bg-white/[0.06]">
            {scene.camera.angle} / {scene.camera.movement}
          </span>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-1">
        {checks.map((check) => (
          <span
            key={check.label}
            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
              check.ok
                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
                : 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
            }`}
          >
            {check.label}
          </span>
        ))}
      </div>

      <div className="mt-2 space-y-1.5">
        {speakerLines.length === 0 ? (
          <p className="text-[11px] text-slate-400">Bu sahnede diyalog yok.</p>
        ) : (
          speakerLines.map((line, lineIndex) => (
            <div key={`${scene.scene_id}-${lineIndex}`} className="text-[11px] leading-snug">
              <span className="font-bold text-slate-700 dark:text-slate-200">{line.speaker}</span>
              <span className="text-slate-400"> → {line.listener || '—'} </span>
              <span className="text-slate-400">({line.range})</span>
              <div className="truncate text-slate-500 dark:text-slate-400">“{line.text}”</div>
            </div>
          ))
        )}
      </div>

      {animated.length > 0 && (
        <div className="mt-2 space-y-1 border-t border-dashed border-slate-200 pt-2 dark:border-white/[0.08]">
          {animated.map((entry) => (
            <div key={`${entry.scene_id}-${entry.character_id}`} className="text-[10px] text-slate-500 dark:text-slate-400">
              <span className="font-semibold text-slate-600 dark:text-slate-300">
                {names[entry.character_id] || entry.character_id}
              </span>{' '}
              · {entry.clips} klip · {entry.keyed_channels} kanal · enerji{' '}
              {entry.profile.energy.toFixed(2)} · jest{' '}
              {entry.profile.gesture_rate.toFixed(2)} · önder el {entry.profile.leading_hand}
            </div>
          ))}
        </div>
      )}

      {lipModes.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {lipModes.map(([characterId, mode]) => (
            <span
              key={`${scene.scene_id}-${characterId}`}
              className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                mode.mode === 'viseme'
                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
                  : 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
              }`}
            >
              {names[characterId] || characterId}:{' '}
              {mode.mode === 'viseme' ? `ölçülmüş viseme (${mode.segments})` : 'basit ağız'}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export const AnimationStep: React.FC<AnimationStepProps> = ({
  project,
  renders,
  voiceStatus,
  onRefresh,
  onNext,
}) => {
  const [engine, setEngine] = useState<'BLENDER_WORKBENCH' | 'BLENDER_EEVEE'>('BLENDER_EEVEE');
  const [synthesizeVoices, setSynthesizeVoices] = useState(true);
  const [currentJob, setCurrentJob] = useState<RenderJob | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const animationRenders = useMemo(
    () =>
      renders
        .filter((job) => job.project_id === project.id && isAnimationRender(job))
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [project.id, renders]
  );
  const latest = latestRenderForProject(renders, project.id, 'animation') || animationRenders[0] || null;

  useEffect(() => {
    setCurrentJob((previous) => {
      if (previous && animationRenders.some((job) => job.id === previous.id)) {
        const updated = animationRenders.find((job) => job.id === previous.id);
        return updated || previous;
      }
      return animationRenders[0] || null;
    });
  }, [animationRenders]);

  useEffect(() => {
    if (!currentJob || !isLiveRender(currentJob)) return;
    let active = true;
    const timer = setInterval(async () => {
      try {
        const updated = await apiService.getRenderJob(currentJob.id);
        if (!active) return;
        setConnectionError(null);
        setCurrentJob(updated);
        if (updated.status === 'completed' || updated.status === 'failed' || updated.status === 'cancelled') {
          await onRefresh();
        }
      } catch {
        setConnectionError('Render durumu sunucudan alınamadı. Bağlantıyı kontrol edin.');
      }
    }, 2000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [currentJob, onRefresh]);

  const startRender = async () => {
    setIsStarting(true);
    setError(null);
    setMessage(null);
    try {
      const job = await apiService.startProjectRender(project.id, engine, synthesizeVoices);
      setCurrentJob(job);
      setMessage('Animasyon render kuyruğuna alındı.');
      await onRefresh();
    } catch (err: any) {
      setError(err.message || 'Animasyon render başlatılamadı.');
    } finally {
      setIsStarting(false);
    }
  };

  const cancelRender = async () => {
    if (!currentJob) return;
    setIsCancelling(true);
    setError(null);
    try {
      await apiService.cancelRenderJob(currentJob.id);
      setMessage('Render iptal edildi.');
      await onRefresh();
    } catch (err: any) {
      setError(err.message || 'Render iptali başarısız oldu.');
    } finally {
      setIsCancelling(false);
    }
  };

  // A `pending` job left behind by an earlier server run never dispatches, and
  // reading it as "in progress" disabled this button forever.
  const isRendering = isLiveRender(currentJob);
  const isStalled = isStalePending(currentJob);
  const completed = animationRenders.some((job) => job.status === 'completed');
  const sceneCount = project.scene_graph?.scenes.length || 0;
  const dialogueCount =
    project.scene_graph?.scenes.reduce((total, scene) => total + scene.dialogues.length, 0) || 0;
  const hasExistingAudio =
    project.scene_graph?.scenes.some((scene) =>
      scene.dialogues.some((dialogue) => Boolean(dialogue.audio_file))
    ) || false;
  const sceneList = project.scene_graph?.scenes || [];
  const characterNames = Object.fromEntries(
    (project.scene_graph?.characters || []).map((character) => [character.id, character.name])
  );
  const animationSummary = (currentJob || latest)?.output_metadata?.animation?.summary;
  const animationPlanned = (currentJob || latest)?.output_metadata?.animation?.planned;

  return (
    <div className="space-y-5">
      <StudioSectionTitle
        title="Animasyon ve Blender render"
        description="Proje SceneGraph’i Blender ile render edilir. Ses sentezi isteğe bağlıdır; ElevenLabs bağlantısı yoksa mevcut ses dosyaları kullanılır."
        action={
          completed ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
              <CheckCircle2 className="h-3 w-3" />
              Animasyon hazır
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[10px] font-bold text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
              <RefreshCw className="h-3 w-3" />
              Render bekliyor
            </span>
          )
        }
      />

      {error && <StudioAlert tone="error">{error}</StudioAlert>}
      {message && <StudioAlert tone="success">{message}</StudioAlert>}
      {connectionError && <StudioAlert tone="error">{connectionError}</StudioAlert>}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <Play className="h-4 w-4 text-[#7367F0]" />
              Render ayarları
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-white/[0.03]">
                <div className="text-lg font-extrabold text-slate-800 dark:text-white">{sceneCount}</div>
                <div className="text-[10px] font-semibold text-slate-400">sahne</div>
              </div>
              <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-white/[0.03]">
                <div className="text-lg font-extrabold text-slate-800 dark:text-white">{dialogueCount}</div>
                <div className="text-[10px] font-semibold text-slate-400">diyalog</div>
              </div>
              <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-white/[0.03]">
                <div className="text-lg font-extrabold text-slate-800 dark:text-white">
                  {Math.round(project.total_duration_seconds)}s
                </div>
                <div className="text-[10px] font-semibold text-slate-400">süre</div>
              </div>
              <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-white/[0.03]">
                <div className="text-lg font-extrabold text-slate-800 dark:text-white">
                  {voiceStatus?.is_configured ? 'API' : 'Yerel'}
                </div>
                <div className="text-[10px] font-semibold text-slate-400">ses kaynağı</div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="text-[11px] font-bold text-slate-600 dark:text-slate-300">
                Render motoru
                <select
                  value={engine}
                  onChange={(event) => setEngine(event.target.value as 'BLENDER_WORKBENCH' | 'BLENDER_EEVEE')}
                  className="vuexy-input mt-1 h-9 w-full px-2 text-xs font-normal"
                >
                  <option value="BLENDER_EEVEE">Blender EEVEE (önerilen)</option>
                  <option value="BLENDER_WORKBENCH">Blender Workbench</option>
                </select>
                <span className="mt-1 block text-[10px] font-normal leading-snug text-slate-400">
                  EEVEE gerçek materyal renklerini, gölgeleri ve ışığı render eder. Workbench
                  hızlıdır; renkleri görüntü katmanından alır ve daha düz görünür.
                </span>
              </label>
              <div className="flex items-end">
                <label className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
                  <input
                    type="checkbox"
                    checked={synthesizeVoices}
                    onChange={(event) => setSynthesizeVoices(event.target.checked)}
                    className="h-4 w-4 accent-[#7367F0]"
                  />
                  ElevenLabs seslerini sentezle
                </label>
              </div>
            </div>

            {!voiceStatus?.is_configured && (
              <StudioAlert tone="warning" title="ElevenLabs bağlantısı yok">
                ELEVENLABS_API_KEY tanımlı değil. Yeni ses üretilemez.
                {hasExistingAudio
                  ? ' Sahnelerde mevcut ses dosyaları bulunduğu için render bunları kullanabilir.'
                  : ' Sahnelerde mevcut ses dosyası yoksa video sessiz kalabilir.'}
              </StudioAlert>
            )}

            {isStalled && (
              <div className="rounded-xl border border-amber-300/60 bg-amber-50 p-3 text-xs leading-relaxed text-amber-800 dark:border-amber-700/50 dark:bg-amber-950/40 dark:text-amber-300">
                <strong className="font-semibold">Bekleyen iş dispatch edilmemiş.</strong>{' '}
                Sunucu yeniden başladığında kuyruktaki iş devam etmez; bu ekran onu
                “render ediliyor” gibi göstermesin diye artık beklenmiyor. Render butonu
                tekrar kullanılabilir.
              </div>
            )}
            <div className="flex gap-2">
              <Button
                onClick={startRender}
                disabled={isStarting || isRendering || isCancelling}
                size="md"
                className="w-full gap-2"
              >
                {isStarting || isRendering ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Film className="h-4 w-4" />
                )}
                {isRendering ? 'Animasyon render ediliyor...' : 'Animasyonu render et'}
              </Button>
              {isRendering && (
                <Button
                  onClick={cancelRender}
                  disabled={isCancelling}
                  variant="destructive"
                  size="md"
                  className="w-full gap-2"
                >
                  {isCancelling ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <AlertTriangle className="h-4 w-4" />
                  )}
                  {isCancelling ? 'İptal ediliyor...' : 'İptal Et'}
                </Button>
              )}
            </div>
            <p className="text-center text-[10px] text-slate-400">
              Bu işlem proje seviyesinde bir RenderJob oluşturur; ilerleme backend’den canlı okunur.
            </p>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2">
                <Volume2 className="h-4 w-4 text-[#7367F0]" />
                Ses durumu
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-[11px]">
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-500 dark:text-slate-400">ElevenLabs</span>
                <span
                  className={`font-bold ${
                    voiceStatus?.is_configured
                      ? 'text-emerald-600 dark:text-emerald-400'
                      : 'text-amber-600 dark:text-amber-400'
                  }`}
                >
                  {voiceStatus?.is_configured ? 'Bağlı' : 'Yapılandırılmadı'}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-500 dark:text-slate-400">Mevcut/önbellek ses</span>
                <span className="font-bold text-slate-700 dark:text-slate-200">
                  {hasExistingAudio ? 'Var' : 'Yok'}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-500 dark:text-slate-400">Model</span>
                <span className="truncate font-semibold text-slate-600 dark:text-slate-300">
                  {voiceStatus?.default_model || '—'}
                </span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Son render</CardTitle>
            </CardHeader>
            <CardContent>
              <RenderStatusPanel
                job={currentJob || latest}
                onRetry={startRender}
                retryLabel="Yeniden render et"
                isRetrying={isStarting}
                showPreview
                videoUrl={currentJob ? apiService.getRenderVideoUrl(currentJob.id) : undefined}
              />
            </CardContent>
          </Card>

          <Button variant="outline" size="md" onClick={onNext} className="w-full gap-2">
            Kompozisyon adımına geç
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Sahne animasyon planı ve render öncesi kontrol</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {sceneList.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-200 p-5 text-center text-xs text-slate-400 dark:border-white/[0.1]">
              Bu projede sahne yok.
            </p>
          ) : (
            sceneList.map((scene, index) => (
              <ScenePlanCard
                key={scene.scene_id}
                scene={scene}
                index={index}
                names={characterNames}
                metadata={(currentJob || latest)?.output_metadata || null}
              />
            ))
          )}
          {animationPlanned === false && (
            <div className="rounded-xl border border-amber-300/60 bg-amber-50 p-3 text-[11px] leading-relaxed text-amber-800 dark:border-amber-700/50 dark:bg-amber-950/40 dark:text-amber-300">
              Bu render’da senaryodan animasyon planı kurulamadı; karakterler eski
              sabit idle hareketiyle render edildi. Hareketler metne göre üretilmedi.
            </div>
          )}
          {animationSummary && (
            <p className="pt-1 text-[10px] leading-relaxed text-slate-500 dark:text-slate-400">              Son render planı:{' '}
              <span className="font-semibold text-slate-600 dark:text-slate-300">
                {animationSummary.clips_total ?? 0} klip
              </span>{' '}
              · {animationSummary.distinct_clips ?? 0} farklı hareket ·{' '}
              {animationSummary.gestures ?? 0} jest ·{' '}
              {animationSummary.dropped_gestures ?? 0} bırakılan
              {animationSummary.clip_usage && (
                <>
                  {' '}
                  · kullanılan:{' '}
                  {Object.entries(animationSummary.clip_usage)
                    .filter(([name]) => !['breathing', 'idle_natural', 'scene_end_settle'].includes(name))
                    .map(([name, count]) => `${name}×${count}`)
                    .join(', ')}
                </>
              )}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Animasyon render geçmişi</CardTitle>
        </CardHeader>
        <CardContent>
          {animationRenders.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-200 p-5 text-center text-xs text-slate-400 dark:border-white/[0.1]">
              Henüz animasyon render kaydı yok.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {animationRenders.slice(0, 6).map((job) => (
                <button
                  key={job.id}
                  type="button"
                  onClick={() => setCurrentJob(job)}
                  className={`rounded-lg border p-3 text-left transition ${
                    currentJob?.id === job.id
                      ? 'border-[#7367F0] bg-[#7367F0]/5'
                      : 'border-slate-200 hover:border-[#7367F0]/40 dark:border-white/[0.08]'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-[10px] text-slate-500">{job.id}</span>
                    <span className="text-[10px] font-bold text-slate-500">{job.status}</span>
                  </div>
                  <div className="mt-1 flex items-center justify-between gap-2 text-[10px] text-slate-400">
                    <span>{formatRenderDuration(job)}</span>
                    <span>{job.created_at.replace('T', ' ').slice(0, 16)}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {!completed && (
        <StudioAlert tone="info">
          <span className="inline-flex items-center gap-1">
            <AlertTriangle className="h-3.5 w-3.5" />
            Animasyon adımı zorunlu değildir. Mevcut ses dosyaları ve sahnelerle doğrudan
            kompozisyona geçebilirsiniz.
          </span>
        </StudioAlert>
      )}
    </div>
  );
};
