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
import { RenderJob, StudioProject, VoiceStatusResponse } from '../../../types/studio';
import { apiService } from '../../../services/api';
import { isActiveRender, isAnimationRender, latestRenderForProject } from '../../../lib/studioWorkspace';
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

export const AnimationStep: React.FC<AnimationStepProps> = ({
  project,
  renders,
  voiceStatus,
  onRefresh,
  onNext,
}) => {
  const [engine, setEngine] = useState<'BLENDER_WORKBENCH' | 'BLENDER_EEVEE'>('BLENDER_WORKBENCH');
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
    if (!currentJob || !isActiveRender(currentJob)) return;
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

  const isRendering = isActiveRender(currentJob);
  const completed = animationRenders.some((job) => job.status === 'completed');
  const sceneCount = project.scene_graph?.scenes.length || 0;
  const dialogueCount =
    project.scene_graph?.scenes.reduce((total, scene) => total + scene.dialogues.length, 0) || 0;
  const hasExistingAudio =
    project.scene_graph?.scenes.some((scene) =>
      scene.dialogues.some((dialogue) => Boolean(dialogue.audio_file))
    ) || false;

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
                  <option value="BLENDER_WORKBENCH">Blender Workbench</option>
                  <option value="BLENDER_EEVEE">Blender EEVEE</option>
                </select>
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
