import React, { useEffect, useRef, useState } from 'react';
import {
  ExternalLink,
  Film,
  Image as ImageIcon,
  Loader2,
  MessageSquare,
  Pencil,
  RefreshCw,
  ThumbsUp,
  Eye,
  AlertTriangle,
  Trash2,
} from 'lucide-react';
import { apiService } from '../services/api';
import { useChannelContext } from '../context/ChannelContext';
import { ChannelVideo, VideoCategory } from '../types/creator';
import { capabilityAllows } from '../lib/capabilities';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { EmptyState } from '../components/ui/EmptyState';
import { Modal } from '../components/ui/Modal';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { formatDate, formatDuration, formatNumber } from '../lib/utils';

const PRIVACY_STYLE: Record<string, string> = {
  public: 'bg-[#28C76F]/10 text-[#28C76F]',
  unlisted: 'bg-[#FF9F43]/10 text-[#FF9F43]',
  private: 'bg-slate-200 text-slate-600 dark:bg-white/[0.08] dark:text-slate-300',
};

const MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024;
const THUMBNAIL_TYPES = ['image/jpeg', 'image/png'];

export const YouTubeVideosPage: React.FC = () => {
  const { activeChannel, connections } = useChannelContext();
  const channelId = activeChannel?.id;
  const connection = connections.find((item) => item.id === activeChannel?.platform_connection_id);
  const uploadAllowed = capabilityAllows(connection, 'upload');
  const deleteAllowed = capabilityAllows(connection, 'comments');
  const thumbnailInputRef = useRef<HTMLInputElement | null>(null);
  const [thumbnailTarget, setThumbnailTarget] = useState<ChannelVideo | null>(null);
  const [isThumbnailUploading, setIsThumbnailUploading] = useState(false);
  const [thumbnailError, setThumbnailError] = useState<string | null>(null);
  const [thumbnailMessage, setThumbnailMessage] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ChannelVideo | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteMessage, setDeleteMessage] = useState<string | null>(null);
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
      const res = await apiService.listChannelVideos(50, undefined, channelId);
      setVideos(res.items);
      apiService
        .listVideoCategories(channelId)
        .then((cat) => setCategories(cat.items))
        .catch(() => setCategories([]));
    } catch (err: any) {
      setError(err.message || 'Kanal videoları alınamadı.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    setVideos([]);
    load();
  }, [channelId]);

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

  const openThumbnailPicker = (video: ChannelVideo) => {
    setThumbnailError(null);
    setThumbnailMessage(null);
    if (!uploadAllowed) {
      setThumbnailError(
        'Video kapağı değiştirmek için YouTube yükleme izni gerekiyor. Mevcut bağlantınız korunur; Bağlı Hesaplar sayfasından izin ekleyebilirsiniz.'
      );
      return;
    }
    setThumbnailTarget(video);
    thumbnailInputRef.current?.click();
  };

  const handleThumbnailFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || !thumbnailTarget) return;
    setThumbnailError(null);
    setThumbnailMessage(null);
    if (!THUMBNAIL_TYPES.includes(file.type)) {
      setThumbnailError('Kapak görseli JPEG veya PNG olmalıdır.');
      return;
    }
    if (file.size > MAX_THUMBNAIL_BYTES) {
      setThumbnailError('Kapak görseli en fazla 2 MB olabilir.');
      return;
    }
    setIsThumbnailUploading(true);
    try {
      await apiService.setVideoThumbnail(thumbnailTarget.video_id, file, channelId);
      setThumbnailMessage(`"${thumbnailTarget.title}" videosunun kapağı güncellendi.`);
      await load();
    } catch (err: any) {
      setThumbnailError(err.message || 'Video kapağı değiştirilemedi.');
    } finally {
      setIsThumbnailUploading(false);
      setThumbnailTarget(null);
    }
  };

  const openDeleteDialog = (video: ChannelVideo) => {
    setDeleteError(null);
    setDeleteMessage(null);
    if (!deleteAllowed) {
      setDeleteError(
        "Videoyu YouTube'dan silmek için yorum yönetimi izni gerekiyor. Mevcut bağlantınız korunur; Bağlı Hesaplar sayfasından izin ekleyebilirsiniz."
      );
      return;
    }
    setDeleteTarget(video);
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await apiService.deleteChannelVideo(deleteTarget.video_id, channelId);
      setVideos((prev) => prev.filter((item) => item.video_id !== deleteTarget.video_id));
      setDeleteMessage(`"${deleteTarget.title}" videosu YouTube'dan silindi.`);
      setDeleteTarget(null);
    } catch (err: any) {
      setDeleteError(err.message || 'Video silinemedi.');
    } finally {
      setIsDeleting(false);
    }
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

      const res = await apiService.updateChannelVideo(editing.video_id, payload, channelId);
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
      <input
        ref={thumbnailInputRef}
        type="file"
        accept="image/jpeg,image/png"
        className="hidden"
        onChange={handleThumbnailFile}
      />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-sm font-bold text-slate-800 dark:text-white">Kanal videoları</h3>
          <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
            YouTube Data API · başlık, açıklama, etiket ve gizlilik değişiklikleri yalnızca sizin onayınızla gönderilir.
            Liste özel ve liste dışı videoları da içerir; kanal kartındaki video sayısı yalnızca herkese açık videoları sayar.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={load} disabled={isLoading} className="gap-1.5 self-end text-xs sm:self-auto">
          {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          Yenile
        </Button>
      </div>

      {thumbnailError && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-300">
          {thumbnailError}
        </div>
      )}
      {thumbnailMessage && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300">
          {thumbnailMessage}
        </div>
      )}
      {deleteError && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-300">
          {deleteError}
        </div>
      )}
      {deleteMessage && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300">
          {deleteMessage}
        </div>
      )}

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
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  <Button variant="outline" size="sm" className="gap-1.5 text-xs" onClick={() => openEditor(video)}>
                    <Pencil className="h-3.5 w-3.5" /> Düzenle
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="gap-1.5 text-xs"
                    onClick={() => openThumbnailPicker(video)}
                    disabled={isThumbnailUploading}
                    title={uploadAllowed ? 'Kapak görselini değiştir' : 'YouTube yükleme izni gerekiyor'}
                  >
                    {isThumbnailUploading && thumbnailTarget?.video_id === video.video_id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <ImageIcon className="h-3.5 w-3.5" />
                    )}
                    Kapak
                  </Button>
                  <a
                    href={`https://www.youtube.com/watch?v=${video.video_id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-[11px] font-semibold text-slate-600 hover:border-[#7367F0]/40 hover:text-[#7367F0] dark:border-white/10 dark:text-slate-300"
                  >
                    İzle <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="gap-1.5 text-xs text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-500/10"
                    onClick={() => openDeleteDialog(video)}
                    disabled={isDeleting && deleteTarget?.video_id === video.video_id}
                    title={deleteAllowed ? "Videoyu YouTube'dan sil" : 'Yorum yönetimi izni gerekiyor'}
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Sil
                  </Button>
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

      <ConfirmDialog
        isOpen={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="Videoyu YouTube'dan sil"
        description={`"${deleteTarget?.title || ''}" videosu YouTube kanalınızdan kalıcı olarak silinecek. Bu işlem geri alınamaz; izlenme, yorum ve gelir geçmişi de kanaldan kaldırılır.`}
        confirmLabel="Videoyu sil"
        isLoading={isDeleting}
      />
    </div>
  );
};
