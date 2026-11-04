import React, { useEffect, useState } from 'react';
import { ArrowRight, CheckCircle2, Loader2, RefreshCw, Save } from 'lucide-react';
import { StudioProject } from '../../../types/studio';
import { formatDate, formatDuration } from '../../../lib/utils';
import { Button } from '../../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { StudioAlert, StudioSectionTitle } from '../StudioShared';
import { projectStatusLabel } from '../../../lib/studioWorkspace';

interface ProjectStepProps {
  project: StudioProject;
  onUpdate: (data: { title: string; description: string }) => Promise<StudioProject>;
  onNext: () => void;
}

export const ProjectStep: React.FC<ProjectStepProps> = ({ project, onUpdate, onNext }) => {
  const [title, setTitle] = useState(project.title);
  const [description, setDescription] = useState(project.description);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setTitle(project.title);
    setDescription(project.description);
    setMessage(null);
    setError(null);
  }, [project.id, project.title, project.description]);

  const isDirty = title.trim() !== project.title || description !== project.description;

  const save = async () => {
    if (!title.trim()) {
      setError('Proje adı zorunludur.');
      return;
    }
    setIsSaving(true);
    setError(null);
    setMessage(null);
    try {
      await onUpdate({ title: title.trim(), description: description.trim() });
      setMessage('Proje bilgileri kaydedildi.');
    } catch (err: any) {
      setError(err.message || 'Proje güncellenemedi.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <StudioSectionTitle
        title="Proje bilgileri"
        description="Üretim akışının geri kalanı bu proje bağlamında ilerler. Proje adı ve açıklaması SceneGraph ile birlikte saklanır."
        action={
          <div className="flex items-center gap-2">
            {isDirty ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[10px] font-bold text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
                <RefreshCw className="h-3 w-3" />
                Kaydedilmemiş değişiklikler
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
                <CheckCircle2 className="h-3 w-3" />
                Güncel
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

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle>Proje detayları</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label htmlFor="workflow-project-title" className="mb-1.5 block text-xs font-bold text-slate-700 dark:text-slate-200">
                Proje adı
              </label>
              <input
                id="workflow-project-title"
                value={title}
                onChange={(event) => {
                  setTitle(event.target.value);
                  setMessage(null);
                }}
                maxLength={200}
                className="vuexy-input h-10 w-full px-3 text-sm"
              />
            </div>
            <div>
              <label htmlFor="workflow-project-description" className="mb-1.5 block text-xs font-bold text-slate-700 dark:text-slate-200">
                Açıklama
              </label>
              <textarea
                id="workflow-project-description"
                value={description}
                onChange={(event) => {
                  setDescription(event.target.value);
                  setMessage(null);
                }}
                maxLength={2000}
                rows={5}
                className="vuexy-input w-full resize-y px-3 py-2 text-sm"
              />
            </div>
            <StudioAlert tone="info">
              Bu adım zorunlu değildir; mevcut bir projeyle devam ediyorsanız doğrudan Hikâye veya
              Sahneler adımına geçebilirsiniz.
            </StudioAlert>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Proje özeti</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-500 dark:text-slate-400">Durum</span>
                <span className="font-bold text-slate-700 dark:text-slate-200">
                  {projectStatusLabel(project.status)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-500 dark:text-slate-400">Sahne</span>
                <span className="font-bold text-slate-700 dark:text-slate-200">{project.scene_count}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-500 dark:text-slate-400">Karakter</span>
                <span className="font-bold text-slate-700 dark:text-slate-200">{project.character_count}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-slate-500 dark:text-slate-400">Süre</span>
                <span className="font-bold text-slate-700 dark:text-slate-200">
                  {formatDuration(project.total_duration_seconds)}
                </span>
              </div>
              <div className="border-t border-slate-100 pt-3 dark:border-white/[0.06]">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-slate-500 dark:text-slate-400">Oluşturuldu</span>
                  <span className="font-semibold text-slate-600 dark:text-slate-300">
                    {formatDate(project.created_at)}
                  </span>
                </div>
                <div className="mt-1.5 flex items-center justify-between gap-2">
                  <span className="text-slate-500 dark:text-slate-400">Güncellendi</span>
                  <span className="font-semibold text-slate-600 dark:text-slate-300">
                    {formatDate(project.updated_at)}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
          <Button size="md" onClick={onNext} className="w-full gap-2">
            Hikâye adımına geç
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};
