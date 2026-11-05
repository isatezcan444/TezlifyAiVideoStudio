import React, { useEffect, useState } from 'react';
import {
  ExternalLink,
  Film,
  Loader2,
  MessageSquare,
  Pencil,
  RefreshCw,
  ThumbsUp,
  Eye,
  AlertTriangle,
} from 'lucide-react';
import { apiService } from '../services/api';
import { ChannelVideo, VideoCategory } from '../types/creator';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { EmptyState } from '../components/ui/EmptyState';
import { Modal } from '../components/ui/Modal';
import { formatDate, formatDuration, formatNumber } from '../lib/utils';

const PRIVACY_STYLE: Record<string, string> = {
  public: 'bg-[#28C76F]/10 text-[#28C76F]',
  unlisted: 'bg-[#FF9F43]/10 text-[#FF9F43]',
  private: 'bg-slate-200 text-slate-600 dark:bg-white/[0.08] dark:text-slate-300',
};

export const YouTubeVideosPage: React.FC = () => {
  const [videos, setVideos] = useState<ChannelVideo[]>([]);
  const [categories, setCategories] = useState<VideoCategory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<ChannelVideo | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [form, setForm] = useState({ title: '', description: '', tags: '', category_id: '', privacy_status: 'public' });

  const load = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiService.listChannelVideos(50);
      setVideos(res.items);
      apiService
        .listVideoCategories()
        .then((cat) => setCategories(cat.items))
        .catch(() => setCategories([]));
    } catch (err: any) {
      setError(err.message || 'Kanal videoları alınamadı.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openEditor = (video: ChannelVideo) => {
    setEditing(video);
    setSaveError(null);
    setForm({
      title: video.title,
      description: video.description || '',
      tags: (video.tags || []).join(', '),
      category_id: video.category_id || '',
      privacy_status: video.privacy_status || 'public',
    });
  };

  const handleSave = async () => {
    if (!editing) return;
    setIsSaving(true);
    setSaveError(null);
    try {
      const payload: Record<string, unknown> = {
        title: form.title,
        description: form.description,
        tags: form.tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
        privacy_status: form.privacy_status,
      };
      if (form.category_id) payload.category_id = form.category_id;

      const res = await apiService.updateChannelVideo(editing.video_id, payload);
      setVideos((prev) => prev.map((item) => (item.video_id === res.video.video_id ? res.video : item)));
      setEditing(null);
    } catch (err: any) {
      setSaveError(err.message || 'Video güncellenemedi.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-sm font-bold text-slate-800 dark:text-white">Kanal videoları</h3>
          <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
            YouTube Data API · başlık, açıklama, etiket ve gizlilik değişiklikleri yalnızca sizin onayınızla gönderilir.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={load} disabled={isLoading} className="gap-1.5 text-xs">
          {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          Yenile
        </Button>
      </div>

      {error ? (
        <EmptyState icon={AlertTriangle} title="Videolar alınamadı" description={error} />
      ) : isLoading ? (
        <div className="flex items-center justify-center py-24 text-xs text-slate-400">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Videolar yükleniyor...
        </div>
      ) : videos.length === 0 ? (
        <EmptyState
          icon={Film}
          title="Kanalda video yok"
          description="YouTube kanalınızda henüz video bulunmuyor. Yerel bir videoyu yükleyerek başlayabilirsiniz."
        />
      ) : (
        <div className="space-y-3">
          {videos.map((video) => (
            <Card key={video.video_id}>
              <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center">
                {video.thumbnail_url ? (
                  <img src={video.thumbnail_url} alt="" className="h-20 w-36 rounded-xl object-cover" />
                ) : (
                  <div className="flex h-20 w-36 items-center justify-center rounded-xl bg-slate-100 text-slate-400 dark:bg-white/[0.05]">
                    <Film className="h-5 w-5" />
                  </div>
                )}
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="truncate text-sm font-bold text-slate-800 dark:text-white">{video.title}</p>
                  <p className="text-[11px] text-slate-400">
                    {video.published_at ? formatDate(video.published_at) : '—'} ·{' '}
                    {formatDuration(video.duration_seconds)} · {video.video_id}
                  </p>
                  <div className="flex flex-wrap items-center gap-3 pt-1 text-[11px] text-slate-500 dark:text-slate-300">
                    <span className="flex items-center gap-1">
                      <Eye className="h-3.5 w-3.5" /> {formatNumber(video.view_count)}
                    </span>
                    <span className="flex items-center gap-1">
                      <ThumbsUp className="h-3.5 w-3.5" /> {formatNumber(video.like_count)}
                    </span>
                    <span className="flex items-center gap-1">
                      <MessageSquare className="h-3.5 w-3.5" /> {formatNumber(video.comment_count)}
                    </span>
                    <span
                      className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold ${
                        PRIVACY_STYLE[video.privacy_status || ''] || PRIVACY_STYLE.private
                      }`}
                    >
                      {video.privacy_status || 'bilinmiyor'}
                    </span>
                    {video.upload_status && video.upload_status !== 'processed' && (
                      <span className="rounded-md bg-[#FF9F43]/10 px-1.5 py-0.5 text-[10px] font-bold text-[#FF9F43]">
                        {video.upload_status}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Button variant="outline" size="sm" className="gap-1.5 text-xs" onClick={() => openEditor(video)}>
                    <Pencil className="h-3.5 w-3.5" /> Düzenle
                  </Button>
                  <a
                    href={`https://www.youtube.com/watch?v=${video.video_id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-[11px] font-semibold text-slate-600 hover:border-[#7367F0]/40 hover:text-[#7367F0] dark:border-white/10 dark:text-slate-300"
                  >
                    İzle <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Modal isOpen={Boolean(editing)} onClose={() => setEditing(null)} title="Video meta verilerini düzenle" maxWidth="lg">
        <div className="space-y-4">
          {saveError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
              {saveError}
            </div>
          )}
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300">Başlık</label>
            <input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              maxLength={100}
              className="vuexy-input w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-white/10 dark:bg-white/[0.03]"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300">Açıklama</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={4}
              className="vuexy-input w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-white/10 dark:bg-white/[0.03]"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300">
              Etiketler (virgülle)
            </label>
            <input
              value={form.tags}
              onChange={(e) => setForm({ ...form, tags: e.target.value })}
              className="vuexy-input w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-white/10 dark:bg-white/[0.03]"
            />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300">Kategori</label>
              <select
                value={form.category_id}
                onChange={(e) => setForm({ ...form, category_id: e.target.value })}
                className="vuexy-input w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-white/10 dark:bg-white/[0.03]"
              >
                <option value="">Değiştirme</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.title}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300">Gizlilik</label>
              <select
                value={form.privacy_status}
                onChange={(e) => setForm({ ...form, privacy_status: e.target.value })}
                className="vuexy-input w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-white/10 dark:bg-white/[0.03]"
              >
                <option value="public">Herkese açık</option>
                <option value="unlisted">Liste dışı</option>
                <option value="private">Özel</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" size="sm" onClick={() => setEditing(null)} disabled={isSaving}>
              Vazgeç
            </Button>
            <Button size="sm" onClick={handleSave} disabled={isSaving || !form.title.trim()}>
              {isSaving ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
              Kaydet
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
