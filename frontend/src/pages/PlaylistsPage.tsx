import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Film,
  ListMusic,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  Youtube,
} from 'lucide-react';
import { apiService } from '../services/api';
import { useChannelContext } from '../context/ChannelContext';
import { ChannelPlaylist, ChannelVideo, PlaylistItem } from '../types/creator';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { EmptyState } from '../components/ui/EmptyState';
import { Modal } from '../components/ui/Modal';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { formatDate } from '../lib/utils';
import { capabilityAllows } from '../lib/capabilities';
import { awaitYouTubeOAuth, openOAuthPopup } from '../lib/youtubeOAuth';

const PRIVACY_LABEL: Record<string, string> = {
  public: 'Herkese açık',
  unlisted: 'Liste dışı',
  private: 'Özel',
};

export const PlaylistsPage: React.FC = () => {
  const { activeChannel, connections, refresh } = useChannelContext();
  const channelId = activeChannel?.id;
  const connection = connections.find((item) => item.id === activeChannel?.platform_connection_id);
  const playlistWriteAllowed = capabilityAllows(connection, 'comments');

  const [playlists, setPlaylists] = useState<ChannelPlaylist[]>([]);
  const [videos, setVideos] = useState<ChannelVideo[]>([]);
  const [selectedId, setSelectedId] = useState<string>('');
  const [items, setItems] = useState<PlaylistItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingItems, setIsLoadingItems] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [itemsError, setItemsError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ title: '', description: '', privacy_status: 'private' });
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [videoToAdd, setVideoToAdd] = useState('');
  const [isGranting, setIsGranting] = useState(false);
  const [grantError, setGrantError] = useState<string | null>(null);

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editForm, setEditForm] = useState({ title: '', description: '', privacy_status: '' });
  const [isEditing, setIsEditing] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [reorderingId, setReorderingId] = useState<string | null>(null);

  const loadPlaylists = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiService.listChannelPlaylists(50, channelId);
      setPlaylists(res.items);
      setSelectedId((current) =>
        current && res.items.some((item) => item.playlist_id === current)
          ? current
          : res.items[0]?.playlist_id || ''
      );
    } catch (err: any) {
      setError(err.message || 'Oynatma listeleri alınamadı.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    setPlaylists([]);
    setItems([]);
    setSelectedId('');
    setActionError(null);
    setActionMessage(null);
    loadPlaylists();
    apiService
      .listChannelVideos(50, undefined, channelId)
      .then((res) => setVideos(res.items))
      .catch(() => setVideos([]));
  }, [channelId]);

  useEffect(() => {
    if (!selectedId) {
      setItems([]);
      return;
    }
    let cancelled = false;
    setIsLoadingItems(true);
    setItemsError(null);
    apiService
      .listPlaylistItems(selectedId, 50, channelId)
      .then((res) => {
        if (!cancelled) setItems(res.items);
      })
      .catch((err: any) => {
        if (!cancelled) setItemsError(err.message || 'Liste videoları alınamadı.');
      })
      .finally(() => {
        if (!cancelled) setIsLoadingItems(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, channelId]);

  const requireWritePermission = (action: string): boolean => {
    if (playlistWriteAllowed) return false;
    setActionMessage(null);
    setActionError(
      `${action} için oynatma listesi yazma izni gerekiyor. İzin vermeden hiçbir yazma çağrısı yapılmaz.`
    );
    return true;
  };

  const handleCreate = async () => {
    if (requireWritePermission('Oynatma listesi oluşturmak')) return;
    if (!createForm.title.trim()) return;
    setIsCreating(true);
    setCreateError(null);
    try {
      const res = await apiService.createPlaylist(
        {
          title: createForm.title.trim(),
          description: createForm.description.trim(),
          privacy_status: createForm.privacy_status,
        },
        channelId
      );
      setIsCreateOpen(false);
      setCreateForm({ title: '', description: '', privacy_status: 'private' });
      await loadPlaylists();
      setSelectedId(res.playlist.playlist_id);
      setActionMessage(`"${res.playlist.title}" oynatma listesi oluşturuldu.`);
    } catch (err: any) {
      setCreateError(err.message || 'Oynatma listesi oluşturulamadı.');
    } finally {
      setIsCreating(false);
    }
  };

  const handleAddVideo = async () => {
    if (!selectedId || !videoToAdd) return;
    if (requireWritePermission('Listeye video eklemek')) return;
    setIsBusy(true);
    setActionError(null);
    setActionMessage(null);
    try {
      await apiService.addVideoToPlaylist(selectedId, videoToAdd, channelId);
      setVideoToAdd('');
      const res = await apiService.listPlaylistItems(selectedId, 50, channelId);
      setItems(res.items);
      setActionMessage('Video oynatma listesine eklendi.');
    } catch (err: any) {
      setActionError(err.message || 'Video oynatma listesine eklenemedi.');
    } finally {
      setIsBusy(false);
    }
  };

  const handleRemove = async (item: PlaylistItem) => {
    if (requireWritePermission('Videoyu listeden çıkarmak')) return;
    setIsBusy(true);
    setActionError(null);
    setActionMessage(null);
    try {
      await apiService.removeVideoFromPlaylist(item.playlist_id, item.video_id, channelId);
      setItems((prev) => prev.filter((entry) => entry.playlist_item_id !== item.playlist_item_id));
      setActionMessage('Video oynatma listesinden çıkarıldı.');
    } catch (err: any) {
      setActionError(err.message || 'Video oynatma listesinden çıkarılamadı.');
    } finally {
      setIsBusy(false);
    }
  };

  const openEditDialog = () => {
    if (!selectedPlaylist) return;
    if (requireWritePermission('Oynatma listesini güncellemek')) return;
    setEditError(null);
    setEditForm({
      title: selectedPlaylist.title,
      description: selectedPlaylist.description || '',
      privacy_status: '',
    });
    setIsEditOpen(true);
  };

  const handleUpdate = async () => {
    if (!selectedPlaylist) return;
    const title = editForm.title.trim();
    if (!title) {
      setEditError('Oynatma listesi adı boş olamaz.');
      return;
    }
    const payload: { title?: string; description?: string; privacy_status?: string } = {};
    if (title !== selectedPlaylist.title) payload.title = title;
    if (editForm.description.trim() !== (selectedPlaylist.description || '')) {
      payload.description = editForm.description.trim();
    }
    if (editForm.privacy_status && editForm.privacy_status !== selectedPlaylist.privacy_status) {
      payload.privacy_status = editForm.privacy_status;
    }
    if (Object.keys(payload).length === 0) {
      setIsEditOpen(false);
      setActionMessage('Değişiklik yapılmadı.');
      return;
    }

    setIsEditing(true);
    setEditError(null);
    try {
      const res = await apiService.updatePlaylist(selectedPlaylist.playlist_id, payload, channelId);
      setPlaylists((prev) =>
        prev.map((item) =>
          item.playlist_id === res.playlist.playlist_id
            ? { ...item, ...res.playlist }
            : item
        )
      );
      setIsEditOpen(false);
      setActionMessage('Oynatma listesi güncellendi.');
    } catch (err: any) {
      setEditError(err.message || 'Oynatma listesi güncellenemedi.');
    } finally {
      setIsEditing(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedPlaylist) return;
    setIsDeleting(true);
    setActionError(null);
    setActionMessage(null);
    try {
      await apiService.deletePlaylist(selectedPlaylist.playlist_id, channelId);
      setIsDeleteOpen(false);
      setItems([]);
      setSelectedId('');
      await loadPlaylists();
      setActionMessage('Oynatma listesi silindi. Videolar kanalda kaldı.');
    } catch (err: any) {
      setActionError(err.message || 'Oynatma listesi silinemedi.');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleMove = async (item: PlaylistItem, direction: -1 | 1) => {
    if (!selectedId) return;
    const index = items.findIndex((entry) => entry.playlist_item_id === item.playlist_item_id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= items.length) return;
    if (requireWritePermission('Liste sırasını değiştirmek')) return;
    setReorderingId(item.playlist_item_id);
    setActionError(null);
    setActionMessage(null);
    try {
      await apiService.movePlaylistItem(selectedId, item.video_id, target, channelId);
      const res = await apiService.listPlaylistItems(selectedId, 50, channelId);
      setItems(res.items);
      setActionMessage('Liste sırası güncellendi.');
    } catch (err: any) {
      setActionError(err.message || 'Liste sırası değiştirilemedi.');
    } finally {
      setReorderingId(null);
    }
  };

  const handleGrantWrite = async () => {
    if (!connection) return;
    setIsGranting(true);
    setGrantError(null);
    try {
      const result = awaitYouTubeOAuth();
      const res = await apiService.grantCapabilities(connection.id, ['comments']);
      openOAuthPopup(res.auth_url, `tezlify_grant_playlists_${connection.id}`);
      const success = await result;
      await refresh();
      if (!success)
        setGrantError('Oynatma listesi izni verilmedi. Mevcut hesap bağlantınız ve okuma izinleri korunuyor.');
    } catch (err: any) {
      setGrantError(err?.message || 'Oynatma listesi izni başlatılamadı.');
    } finally {
      setIsGranting(false);
    }
  };

  const selectedPlaylist = playlists.find((item) => item.playlist_id === selectedId);
  const availableVideos = videos.filter(
    (video) => !items.some((item) => item.video_id === video.video_id)
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-sm font-bold text-slate-800 dark:text-white">Oynatma listeleri</h3>
          <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
            YouTube Data API · liste oluşturma ve video ekleme yalnızca sizin onayınızla gönderilir.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={loadPlaylists}
            disabled={isLoading}
            className="gap-1.5 text-xs"
          >
            {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Yenile
          </Button>
          <Button
            size="sm"
            className="gap-1.5 text-xs"
            onClick={() => {
              if (requireWritePermission('Oynatma listesi oluşturmak')) return;
              setCreateError(null);
              setIsCreateOpen(true);
            }}
          >
            <Plus className="h-3.5 w-3.5" /> Yeni liste
          </Button>
        </div>
      </div>

      {!playlistWriteAllowed && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-500/20 dark:bg-amber-500/10">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
              <div>
                <p className="text-xs font-bold text-amber-700 dark:text-amber-300">
                  Oynatma listesi yazma izni yok
                </p>
                <p className="text-[11px] text-amber-600 dark:text-amber-200">
                  Listeleri görüntüleyebilirsiniz; oluşturma, video ekleme ve çıkarma için
                  <span className="font-semibold"> youtube.force-ssl </span>
                  izni gerekiyor. Mevcut bağlantınız korunur.
                </p>
                {grantError && <p className="mt-1 text-[11px] text-rose-500">{grantError}</p>}
              </div>
            </div>
            <Button size="sm" variant="outline" onClick={handleGrantWrite} disabled={isGranting}>
              {isGranting ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
              İzin ver
            </Button>
          </div>
        </div>
      )}

      {actionError && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-300">
          {actionError}
        </div>
      )}
      {actionMessage && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300">
          {actionMessage}
        </div>
      )}

      {error ? (
        <EmptyState icon={AlertTriangle} title="Oynatma listeleri alınamadı" description={error} />
      ) : isLoading ? (
        <div className="flex items-center justify-center py-24 text-xs text-slate-400">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Oynatma listeleri yükleniyor...
        </div>
      ) : playlists.length === 0 ? (
        <EmptyState
          icon={ListMusic}
          title="Oynatma listesi yok"
          description="Kanalınızda henüz oynatma listesi bulunmuyor. Yeni bir liste oluşturarak videolarınızı düzenleyebilirsiniz."
          actionLabel="Yeni liste oluştur"
          onAction={() => {
            if (requireWritePermission('Oynatma listesi oluşturmak')) return;
            setCreateError(null);
            setIsCreateOpen(true);
          }}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
          <Card>
            <CardContent className="p-2">
              <ul className="space-y-1">
                {playlists.map((playlist) => (
                  <li key={playlist.playlist_id}>
                    <button
                      onClick={() => setSelectedId(playlist.playlist_id)}
                      className={`w-full rounded-lg px-3 py-2 text-left transition-colors ${
                        playlist.playlist_id === selectedId
                          ? 'bg-[#7367F0]/10 text-[#7367F0] dark:bg-[#7367F0]/20 dark:text-[#A59DF8]'
                          : 'text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-white/[0.04]'
                      }`}
                    >
                      <span className="block truncate text-xs font-bold">{playlist.title}</span>
                      <span className="text-[10px] text-slate-400">
                        {playlist.item_count != null ? `${playlist.item_count} video` : 'Video sayısı bilinmiyor'}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          <div className="space-y-3">
            <Card>
              <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold text-slate-800 dark:text-white">
                    {selectedPlaylist?.title || 'Liste seçin'}
                  </p>
                  <p className="text-[11px] text-slate-400">
                    {selectedPlaylist?.description || 'Açıklama yok'}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="gap-1.5 text-xs"
                    onClick={openEditDialog}
                    disabled={!selectedPlaylist || !playlistWriteAllowed}
                  >
                    <Pencil className="h-3.5 w-3.5" /> Düzenle
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="gap-1.5 text-xs text-rose-500 hover:text-rose-600"
                    onClick={() => {
                      if (requireWritePermission('Oynatma listesini silmek')) return;
                      setIsDeleteOpen(true);
                    }}
                    disabled={!selectedPlaylist || !playlistWriteAllowed}
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Sil
                  </Button>
                  <select
                    value={videoToAdd}
                    onChange={(e) => setVideoToAdd(e.target.value)}
                    disabled={!playlistWriteAllowed || isBusy || availableVideos.length === 0}
                    className="vuexy-input max-w-[220px] rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs disabled:opacity-60 dark:border-white/10 dark:bg-white/[0.03]"
                  >
                    <option value="">Video seç</option>
                    {availableVideos.map((video) => (
                      <option key={video.video_id} value={video.video_id}>
                        {video.title}
                      </option>
                    ))}
                  </select>
                  <Button
                    size="sm"
                    className="gap-1.5 text-xs"
                    onClick={handleAddVideo}
                    disabled={!videoToAdd || isBusy || !playlistWriteAllowed}
                  >
                    {isBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                    Ekle
                  </Button>
                </div>
              </CardContent>
            </Card>

            {itemsError ? (
              <EmptyState icon={AlertTriangle} title="Liste videoları alınamadı" description={itemsError} />
            ) : isLoadingItems ? (
              <div className="flex items-center justify-center py-16 text-xs text-slate-400">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Listeye yükleniyor...
              </div>
            ) : items.length === 0 ? (
              <EmptyState
                icon={Film}
                title="Liste boş"
                description="Bu oynatma listesinde video yok. Kanal videolarınızdan birini seçerek ekleyebilirsiniz."
              />
            ) : (
              <div className="space-y-2">
                {items.map((item, index) => (
                  <Card key={item.playlist_item_id}>
                    <CardContent className="flex items-center gap-3 p-3">
                      {item.thumbnail_url ? (
                        <img src={item.thumbnail_url} alt="" className="h-14 w-24 rounded-lg object-cover" />
                      ) : (
                        <div className="flex h-14 w-24 items-center justify-center rounded-lg bg-slate-100 text-slate-400 dark:bg-white/[0.05]">
                          <Film className="h-4 w-4" />
                        </div>
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-bold text-slate-800 dark:text-white">{item.title}</p>
                        <p className="text-[10px] text-slate-400">
                          {item.published_at ? formatDate(item.published_at) : '—'} · {item.video_id}
                          {item.position != null ? ` · sıra ${item.position + 1}` : ''}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-col">
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label="Yukarı taşı"
                          className="h-6 px-1.5"
                          onClick={() => handleMove(item, -1)}
                          disabled={
                            index === 0 ||
                            reorderingId !== null ||
                            isBusy ||
                            !playlistWriteAllowed
                          }
                        >
                          <ArrowUp className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label="Aşağı taşı"
                          className="h-6 px-1.5"
                          onClick={() => handleMove(item, 1)}
                          disabled={
                            index === items.length - 1 ||
                            reorderingId !== null ||
                            isBusy ||
                            !playlistWriteAllowed
                          }
                        >
                          <ArrowDown className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="gap-1.5 text-[11px] text-rose-500 hover:text-rose-600"
                        onClick={() => handleRemove(item)}
                        disabled={isBusy || !playlistWriteAllowed}
                      >
                        <Trash2 className="h-3.5 w-3.5" /> Çıkar
                      </Button>
                      <a
                        href={`https://www.youtube.com/watch?v=${item.video_id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 hover:border-[#7367F0]/40 hover:text-[#7367F0] dark:border-white/10 dark:text-slate-300"
                      >
                        <Youtube className="h-3.5 w-3.5" /> İzle
                      </a>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Yeni oynatma listesi"
        maxWidth="lg"
      >
        <div className="space-y-4">
          {createError && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-300">
              {createError}
            </div>
          )}
          <div>
            <label
              htmlFor="playlist-title"
              className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300"
            >
              Ad
            </label>
            <input
              id="playlist-title"
              value={createForm.title}
              onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })}
              maxLength={150}
              className="vuexy-input w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-white/10 dark:bg-white/[0.03]"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300">Açıklama</label>
            <textarea
              value={createForm.description}
              onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
              rows={3}
              maxLength={5000}
              className="vuexy-input w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-white/10 dark:bg-white/[0.03]"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300">Gizlilik</label>
            <select
              value={createForm.privacy_status}
              onChange={(e) => setCreateForm({ ...createForm, privacy_status: e.target.value })}
              className="vuexy-input w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-white/10 dark:bg-white/[0.03]"
            >
              <option value="private">{PRIVACY_LABEL.private}</option>
              <option value="unlisted">{PRIVACY_LABEL.unlisted}</option>
              <option value="public">{PRIVACY_LABEL.public}</option>
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" size="sm" onClick={() => setIsCreateOpen(false)} disabled={isCreating}>
              Vazgeç
            </Button>
            <Button size="sm" onClick={handleCreate} disabled={isCreating || !createForm.title.trim()}>
              {isCreating ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
              Oluştur
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
        title="Oynatma listesini düzenle"
        maxWidth="lg"
      >
        <div className="space-y-4">
          {editError && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-300">
              {editError}
            </div>
          )}
          <div>
            <label
              htmlFor="edit-playlist-title"
              className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300"
            >
              Ad
            </label>
            <input
              id="edit-playlist-title"
              value={editForm.title}
              onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
              maxLength={150}
              className="vuexy-input w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-white/10 dark:bg-white/[0.03]"
            />
          </div>
          <div>
            <label
              htmlFor="edit-playlist-description"
              className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300"
            >
              Açıklama
            </label>
            <textarea
              id="edit-playlist-description"
              value={editForm.description}
              onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
              rows={3}
              maxLength={5000}
              className="vuexy-input w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-white/10 dark:bg-white/[0.03]"
            />
          </div>
          <div>
            <label
              htmlFor="edit-playlist-privacy"
              className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300"
            >
              Gizlilik
            </label>
            <select
              id="edit-playlist-privacy"
              value={editForm.privacy_status}
              onChange={(e) => setEditForm({ ...editForm, privacy_status: e.target.value })}
              className="vuexy-input w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-white/10 dark:bg-white/[0.03]"
            >
              <option value="">Değiştirme</option>
              <option value="private">{PRIVACY_LABEL.private}</option>
              <option value="unlisted">{PRIVACY_LABEL.unlisted}</option>
              <option value="public">{PRIVACY_LABEL.public}</option>
            </select>
            {selectedPlaylist?.privacy_status && (
              <p className="mt-1 text-[10px] text-slate-400">
                Geçerli: {PRIVACY_LABEL[selectedPlaylist.privacy_status] || selectedPlaylist.privacy_status}
              </p>
            )}
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" size="sm" onClick={() => setIsEditOpen(false)} disabled={isEditing}>
              Vazgeç
            </Button>
            <Button size="sm" onClick={handleUpdate} disabled={isEditing || !editForm.title.trim()}>
              {isEditing ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
              Kaydet
            </Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
        onConfirm={handleDelete}
        title="Oynatma listesini sil"
        description={`"${selectedPlaylist?.title || ''}" listesi YouTube kanalınızdan kalıcı olarak silinecek. Listeye eklenmiş videolar kanalda kalmaya devam eder.`}
        confirmLabel="Listeyi sil"
        isLoading={isDeleting}
      />
    </div>
  );
};
