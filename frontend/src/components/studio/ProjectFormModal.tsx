import React, { useEffect, useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/button';
import { StudioProject } from '../../types/studio';
import { StudioAlert } from './StudioShared';

interface ProjectFormModalProps {
  isOpen: boolean;
  project?: StudioProject | null;
  onClose: () => void;
  onSubmit: (data: { title: string; description: string }) => Promise<void>;
}

export const ProjectFormModal: React.FC<ProjectFormModalProps> = ({
  isOpen,
  project,
  onClose,
  onSubmit,
}) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setTitle(project?.title || '');
    setDescription(project?.description || '');
    setError(null);
  }, [isOpen, project]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!title.trim()) {
      setError('Proje adı zorunludur.');
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      await onSubmit({ title: title.trim(), description: description.trim() });
      onClose();
    } catch (err: any) {
      setError(err.message || 'Proje kaydedilemedi.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={project ? 'Projeyi Düzenle' : 'Yeni Video Projesi'}
      maxWidth="lg"
    >
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label
            htmlFor="studio-project-title"
            className="mb-1.5 block text-xs font-bold text-slate-700 dark:text-slate-200"
          >
            Proje adı
          </label>
          <input
            id="studio-project-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            maxLength={200}
            autoFocus
            placeholder="Örn. Ali ve Ayşe'nin Kafe Buluşması"
            className="vuexy-input h-10 w-full px-3 text-sm"
          />
        </div>
        <div>
          <label
            htmlFor="studio-project-description"
            className="mb-1.5 block text-xs font-bold text-slate-700 dark:text-slate-200"
          >
            Açıklama <span className="font-medium text-slate-400">(isteğe bağlı)</span>
          </label>
          <textarea
            id="studio-project-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            maxLength={2000}
            rows={3}
            placeholder="Hikâyenin kısa özeti, hedef kitle veya üretim notları..."
            className="vuexy-input w-full resize-y px-3 py-2 text-sm"
          />
        </div>

        {!project && (
          <StudioAlert tone="info">
            Proje, düzenlenebilir bir başlangıç SceneGraph’i ile oluşturulur. Bir sonraki adımda
            hikâye üretebilir veya sahneleri elle düzenleyebilirsiniz.
          </StudioAlert>
        )}

        {error && <StudioAlert tone="error">{error}</StudioAlert>}

        <div className="flex flex-col-reverse gap-2 pt-1 sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" size="md" onClick={onClose} disabled={isSaving}>
            Vazgeç
          </Button>
          <Button type="submit" size="md" disabled={isSaving} className="gap-2">
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            {project ? 'Değişiklikleri Kaydet' : 'Projeyi Oluştur'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
