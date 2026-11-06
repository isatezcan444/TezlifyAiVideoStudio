import React, { useState, useEffect, useRef } from 'react';
import { MediaAsset } from '../../types/media';
import { PrivacyStatus, PublishRecord } from '../../types/publish';
import { ScheduledPublish } from '../../types/schedule';
import { ChannelPlaylist } from '../../types/creator';
import { apiService } from '../../services/api';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/button';
import { Spinner } from '../ui/Spinner';
import { Youtube, ImagePlus, Calendar, ListVideo, CheckCircle2, X } from 'lucide-react';

interface YouTubePublishModalProps {
  asset: MediaAsset | null;
  isOpen: boolean;
  onClose: () => void;
  onPublishStarted: (record: PublishRecord) => void;
  channelId?: string | null;
  channelName?: string | null;
  playlistWriteAllowed?: boolean;
}

const YOUTUBE_CATEGORIES = [
  { id: '22', name: 'People & Blogs (Kişiler ve Bloglar)' },
  { id: '28', name: 'Science & Technology (Bilim ve Teknoloji)' },
  { id: '24', name: 'Entertainment (Eğlence)' },
  { id: '20', name: 'Gaming (Oyun)' },
  { id: '1', name: 'Film & Animation (Film ve Animasyon)' },
  { id: '10', name: 'Music (Müzik)' },
  { id: '27', name: 'Education (Eğitim)' },
  { id: '26', name: 'Howto & Style (Nasıl Yapılır ve Stil)' },
];

const COMMON_TIMEZONES = [
  'Europe/Istanbul',
  'UTC',
  'Europe/London',
  'Europe/Berlin',
  'Europe/Paris',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Asia/Dubai',
  'Asia/Tokyo',
  'Asia/Singapore',
  'Australia/Sydney',
];

const formatForDateTimeLocal = (date: Date) => {
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
};

export const YouTubePublishModal: React.FC<YouTubePublishModalProps> = ({
  asset,
  isOpen,
  onClose,
  onPublishStarted,
  channelId = null,
  channelName = null,
  playlistWriteAllowed = true,
}) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [categoryId, setCategoryId] = useState('22');
  const [privacyStatus, setPrivacyStatus] = useState<PrivacyStatus>('private');

  const [mode, setMode] = useState<'now' | 'schedule'>('now');
  const [scheduledDate, setScheduledDate] = useState('');
  const [timezone, setTimezone] = useState('Europe/Istanbul');

  const [playlists, setPlaylists] = useState<ChannelPlaylist[]>([]);
  const [playlistId, setPlaylistId] = useState('');
  const [isLoadingPlaylists, setIsLoadingPlaylists] = useState(false);
  const [playlistError, setPlaylistError] = useState<string | null>(null);

  const [customThumbnailPath, setCustomThumbnailPath] = useState<string | null>(null);
  const [thumbnailPreview, setThumbnailPreview] = useState<string | null>(null);
  const [isThumbnailUploading, setIsThumbnailUploading] = useState(false);
  const [thumbnailError, setThumbnailError] = useState<string | null>(null);
  const thumbnailInputRef = useRef<HTMLInputElement>(null);
  const previewUrlRef = useRef<string | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scheduledSuccess, setScheduledSuccess] = useState<ScheduledPublish | null>(null);

  const clearPreviewUrl = () => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
  };

  useEffect(() => {
    try {
      const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (userTz) setTimezone(userTz);
    } catch {
      setTimezone('Europe/Istanbul');
    }
  }, []);

  useEffect(() => {
    if (asset) {
      const defaultTitle = asset.original_filename.replace(/\.[^/.]+$/, '');
      setTitle(defaultTitle.slice(0, 100));
      setDescription(`Tezlify Creator Studio ile hazırlandı.\n\nDosya: ${asset.original_filename}`);
      setTagsInput('tezlify, animation, ai video');
      setCategoryId('22');
      setPrivacyStatus('private');
      setMode('now');
      setError(null);
      setScheduledSuccess(null);
      setPlaylistId('');
      setCustomThumbnailPath(null);
      setThumbnailError(null);
      clearPreviewUrl();
      setThumbnailPreview(null);

      const nextTime = new Date(Date.now() + 2 * 60 * 60 * 1000);
      nextTime.setMinutes(Math.ceil(nextTime.getMinutes() / 15) * 15, 0, 0);
      setScheduledDate(formatForDateTimeLocal(nextTime));
    }
  }, [asset]);

  useEffect(() => () => clearPreviewUrl(), []);

  useEffect(() => {
    if (!isOpen || !channelId) {
      setPlaylists([]);
      return;
    }
    let cancelled = false;
    setIsLoadingPlaylists(true);
    setPlaylistError(null);
    apiService
      .listChannelPlaylists(50, channelId)
      .then((res) => {
        if (cancelled) return;
        setPlaylists(res.items || []);
      })
      .catch((err: any) => {
        if (cancelled) return;
        setPlaylists([]);
        setPlaylistError(err?.message || 'Oynatma listeleri alınamadı.');
      })
      .finally(() => {
        if (!cancelled) setIsLoadingPlaylists(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, channelId]);

  if (!asset) return null;

  const handleThumbnailSelected = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    if (file.type !== 'image/jpeg' && file.type !== 'image/png') {
      setThumbnailError('Kapak görseli JPEG veya PNG olmalıdır.');
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setThumbnailError('Kapak görseli en fazla 2 MB olabilir.');
      return;
    }

    setThumbnailError(null);
    setIsThumbnailUploading(true);
    try {
      const uploaded = await apiService.uploadCustomThumbnail(asset.id, file);
      clearPreviewUrl();
      const objectUrl = URL.createObjectURL(file);
      previewUrlRef.current = objectUrl;
      setThumbnailPreview(objectUrl);
      setCustomThumbnailPath(uploaded.thumbnail_path);
    } catch (err: any) {
      setThumbnailError(err?.message || 'Kapak görseli yüklenemedi.');
    } finally {
      setIsThumbnailUploading(false);
    }
  };

  const clearCustomThumbnail = () => {
    clearPreviewUrl();
    setThumbnailPreview(null);
    setCustomThumbnailPath(null);
    setThumbnailError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!channelId) {
      setError('Hedef kanal seçili değil. Önce Bağlı Hesaplar ekranından bir kanal seçin.');
      return;
    }
    if (!title.trim()) {
      setError('Lütfen bir video başlığı girin.');
      return;
    }

    const tags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);
    const thumbnailPath = customThumbnailPath || asset.thumbnail_path || null;
    const selectedPlaylistId = playlistId || null;

    if (mode === 'schedule') {
      if (!scheduledDate) {
        setError('Lütfen geçerli bir yayın tarihi ve saati seçin.');
        return;
      }
      const dateObj = new Date(scheduledDate);
      if (isNaN(dateObj.getTime())) {
        setError('Tarih biçimi geçersiz.');
        return;
      }
      if (dateObj.getTime() <= Date.now()) {
        setError('Yayın tarihi ileri bir zaman olmalıdır.');
        return;
      }
    }

    setError(null);
    setIsSubmitting(true);

    try {
      if (mode === 'schedule') {
        const created = await apiService.createSchedule({
          media_asset_id: asset.id,
          title: title.trim(),
          description: description.trim(),
          tags,
          category_id: categoryId,
          privacy_status: privacyStatus,
          thumbnail_path: thumbnailPath,
          playlist_id: selectedPlaylistId,
          scheduled_at: new Date(scheduledDate).toISOString(),
          timezone,
          max_attempts: 3,
          channel_id: channelId,
        });
        setScheduledSuccess(created);
        return;
      }

      const record = await apiService.startPublish({
        media_asset_id: asset.id,
        title: title.trim(),
        description: description.trim(),
        tags,
        category_id: categoryId,
        privacy_status: privacyStatus,
        thumbnail_path: thumbnailPath,
        playlist_id: selectedPlaylistId,
        channel_id: channelId,
      });

      onPublishStarted(record);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Yayınlama başlatılırken bir hata oluştu.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes >= 1024 * 1024 * 1024) {
      return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const activeThumbnailSrc =
    thumbnailPreview || (asset.thumbnail_path ? apiService.getThumbnailUrl(asset.id) : null);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="YouTube'da Yayınla" maxWidth="lg">
      {scheduledSuccess ? (
        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-xl border border-emerald-500/25 bg-emerald-500/10 p-4">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
            <div>
              <p className="text-sm font-semibold text-emerald-700 dark:text-emerald-300">
                Yayın planlandı
              </p>
              <p className="mt-1 text-xs text-emerald-700/80 dark:text-emerald-300/80">
                {new Date(scheduledSuccess.scheduled_at_utc).toLocaleString('tr-TR')} ({scheduledSuccess.timezone})
              </p>
              <p className="mt-2 text-xs text-[#828092] dark:text-[#908DA1]">
                Plan, Planlayıcı sayfasından izlenebilir; saat geldiğinde yükleme otomatik başlar.
              </p>
            </div>
          </div>
          <div className="flex justify-end">
            <Button type="button" onClick={onClose} className="text-xs">
              Kapat
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-600 dark:text-rose-400">
            {error}
          </div>
        )}

        {/* Target channel */}
        <div className="flex items-center gap-2.5 rounded-xl border border-[#7367F0]/25 bg-[#7367F0]/5 p-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#7367F0]/15 text-[#7367F0]">
            <Youtube className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-wider text-[#7367F0]">Hedef Kanal</p>
            <p className="truncate text-xs font-semibold text-[#4B465C] dark:text-[#DBD7EC]">
              {channelName || 'Kanal seçilmedi'}
            </p>
          </div>
          {!channelId && (
            <span className="ml-auto rounded-md bg-rose-500/10 px-2 py-0.5 text-[10px] font-bold text-rose-500">
              Kanal yok
            </span>
          )}
        </div>

        {/* Video Info Summary Box */}
        <div className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 dark:bg-[#25293C] border border-slate-200 dark:border-slate-800">
          <div className="w-16 h-10 rounded bg-black/20 dark:bg-black/40 overflow-hidden flex items-center justify-center shrink-0">
            {asset.thumbnail_path ? (
              <img
                src={apiService.getThumbnailUrl(asset.id)}
                alt={asset.original_filename}
                className="w-full h-full object-cover"
              />
            ) : (
              <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <h5 className="text-xs font-semibold text-[#4B465C] dark:text-[#DBD7EC] truncate">
              {asset.original_filename}
            </h5>
            <div className="flex items-center gap-3 text-[11px] text-[#828092] dark:text-[#908DA1] mt-0.5">
              <span>{formatFileSize(asset.file_size_bytes)}</span>
              {asset.metadata?.resolution_label && <span>• {asset.metadata.resolution_label}</span>}
              {asset.metadata?.duration_seconds && <span>• {Math.round(asset.metadata.duration_seconds)}s</span>}
            </div>
          </div>
        </div>

        {/* Custom thumbnail */}
        <div>
          <label className="mb-1 block text-xs font-medium text-[#4B465C] dark:text-[#DBD7EC]">Kapak Görseli</label>
          <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-[#25293C]">
            <div className="h-16 w-28 shrink-0 overflow-hidden rounded-lg bg-black/20 dark:bg-black/40">
              {activeThumbnailSrc ? (
                <img src={activeThumbnailSrc} alt="Kapak önizleme" className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-slate-400">
                  <ImagePlus className="h-5 w-5" />
                </div>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[11px] text-[#828092] dark:text-[#908DA1]">
                {customThumbnailPath
                  ? 'Özel kapak yüklendi.'
                  : 'Videodan üretilen kapak kullanılacak.'}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <input
                  ref={thumbnailInputRef}
                  type="file"
                  accept="image/jpeg,image/png"
                  className="hidden"
                  onChange={handleThumbnailSelected}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="text-[11px]"
                  disabled={isThumbnailUploading}
                  onClick={() => thumbnailInputRef.current?.click()}
                >
                  {isThumbnailUploading ? <Spinner size="sm" /> : <ImagePlus className="h-3.5 w-3.5" />}
                  <span className="ml-1.5">{customThumbnailPath ? 'Değiştir' : 'Özel kapak seç'}</span>
                </Button>
                {customThumbnailPath && (
                  <button
                    type="button"
                    onClick={clearCustomThumbnail}
                    className="inline-flex items-center gap-1 text-[11px] text-[#828092] hover:text-rose-500"
                  >
                    <X className="h-3 w-3" /> Kaldır
                  </button>
                )}
              </div>
              <p className="mt-1 text-[10px] text-[#828092] dark:text-[#908DA1]">JPEG veya PNG, en fazla 2 MB.</p>
              {thumbnailError && <p className="mt-1 text-[11px] text-rose-500">{thumbnailError}</p>}
            </div>
          </div>
        </div>

        {/* Title Input */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-medium text-[#4B465C] dark:text-[#DBD7EC]">Video Başlığı *</label>
            <span className="text-[11px] text-[#828092] dark:text-[#908DA1]">{title.length}/100</span>
          </div>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={100}
            required
            placeholder="Video için çekici bir başlık yazın..."
            className="w-full px-3 py-2 text-sm rounded-lg bg-white dark:bg-[#25293C] border border-slate-200 dark:border-slate-700 text-[#4B465C] dark:text-[#DBD7EC] focus:outline-none focus:ring-2 focus:ring-[#7367F0]/40 focus:border-[#7367F0]"
          />
        </div>

        {/* Description Input */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-medium text-[#4B465C] dark:text-[#DBD7EC]">Açıklama (Description)</label>
            <span className="text-[11px] text-[#828092] dark:text-[#908DA1]">{description.length}/5000</span>
          </div>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={5000}
            rows={3}
            placeholder="Videonun içeriği, zaman damgaları ve bağlantılar..."
            className="w-full px-3 py-2 text-sm rounded-lg bg-white dark:bg-[#25293C] border border-slate-200 dark:border-slate-700 text-[#4B465C] dark:text-[#DBD7EC] focus:outline-none focus:ring-2 focus:ring-[#7367F0]/40 focus:border-[#7367F0] resize-none"
          />
        </div>

        {/* Tags Input */}
        <div>
          <label className="block text-xs font-medium text-[#4B465C] dark:text-[#DBD7EC] mb-1">
            Etiketler (Virgülle ayırın)
          </label>
          <input
            type="text"
            value={tagsInput}
            onChange={(e) => setTagsInput(e.target.value)}
            placeholder="ör. vlog, eğitim, teknoloji"
            className="w-full px-3 py-2 text-sm rounded-lg bg-white dark:bg-[#25293C] border border-slate-200 dark:border-slate-700 text-[#4B465C] dark:text-[#DBD7EC] focus:outline-none focus:ring-2 focus:ring-[#7367F0]/40 focus:border-[#7367F0]"
          />
        </div>

        {/* Category & Privacy Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-[#4B465C] dark:text-[#DBD7EC] mb-1">Kategori</label>
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg bg-white dark:bg-[#25293C] border border-slate-200 dark:border-slate-700 text-[#4B465C] dark:text-[#DBD7EC] focus:outline-none focus:ring-2 focus:ring-[#7367F0]/40 focus:border-[#7367F0]"
            >
              {YOUTUBE_CATEGORIES.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-[#4B465C] dark:text-[#DBD7EC] mb-1">Gizlilik Durumu</label>
            <select
              value={privacyStatus}
              onChange={(e) => setPrivacyStatus(e.target.value as PrivacyStatus)}
              className="w-full px-3 py-2 text-sm rounded-lg bg-white dark:bg-[#25293C] border border-slate-200 dark:border-slate-700 text-[#4B465C] dark:text-[#DBD7EC] focus:outline-none focus:ring-2 focus:ring-[#7367F0]/40 focus:border-[#7367F0]"
            >
              <option value="private">Gizli (Private - Yalnızca Siz)</option>
              <option value="unlisted">Liste Dışı (Unlisted - Bağlantısı Olanlar)</option>
              <option value="public">Herkese Açık (Public)</option>
            </select>
          </div>
        </div>

        {/* Playlist */}
        <div>
          <label className="mb-1 flex items-center gap-1.5 text-xs font-medium text-[#4B465C] dark:text-[#DBD7EC]">
            <ListVideo className="h-3.5 w-3.5" /> Oynatma Listesi
          </label>
          <select
            value={playlistId}
            onChange={(e) => setPlaylistId(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-lg bg-white dark:bg-[#25293C] border border-slate-200 dark:border-slate-700 text-[#4B465C] dark:text-[#DBD7EC] focus:outline-none focus:ring-2 focus:ring-[#7367F0]/40 focus:border-[#7367F0]"
            disabled={!playlistWriteAllowed || isLoadingPlaylists}
          >
            <option value="">Oynatma listesine ekleme</option>
            {playlists.map((playlist) => (
              <option key={playlist.playlist_id} value={playlist.playlist_id}>
                {playlist.title}{playlist.item_count != null ? ` (${playlist.item_count} video)` : ''}
              </option>
            ))}
          </select>
          {isLoadingPlaylists && <p className="mt-1 text-[11px] text-[#828092]">Oynatma listeleri yükleniyor...</p>}
          {!isLoadingPlaylists && playlistError && <p className="mt-1 text-[11px] text-rose-500">{playlistError}</p>}
          {!isLoadingPlaylists && !playlistError && playlists.length === 0 && (
            <p className="mt-1 text-[11px] text-[#828092]">Kanala ait oynatma listesi bulunamadı.</p>
          )}
          {!playlistWriteAllowed && (
            <p className="mt-1 text-[11px] text-amber-600 dark:text-amber-400">
              Oynatma listesine eklemek için YouTube yazma izni (comments capability) gerekir.
            </p>
          )}
        </div>

        {/* Publish timing */}
        <div>
          <label className="mb-1.5 block text-xs font-medium text-[#4B465C] dark:text-[#DBD7EC]">Yayın Zamanı</label>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setMode('now')}
              className={`rounded-xl border px-3 py-2 text-left text-xs transition-all ${
                mode === 'now'
                  ? 'border-[#7367F0] bg-[#7367F0]/10 text-[#7367F0] ring-1 ring-[#7367F0]'
                  : 'border-slate-200 dark:border-slate-700'
              }`}
            >
              <span className="block font-semibold">Hemen yayınla</span>
              <span className="mt-0.5 block text-[10px] text-[#828092]">Yükleme hemen başlar</span>
            </button>
            <button
              type="button"
              onClick={() => setMode('schedule')}
              className={`rounded-xl border px-3 py-2 text-left text-xs transition-all ${
                mode === 'schedule'
                  ? 'border-[#7367F0] bg-[#7367F0]/10 text-[#7367F0] ring-1 ring-[#7367F0]'
                  : 'border-slate-200 dark:border-slate-700'
              }`}
            >
              <span className="flex items-center gap-1 font-semibold"><Calendar className="h-3.5 w-3.5" /> İleri bir tarihe planla</span>
              <span className="mt-0.5 block text-[10px] text-[#828092]">Planlayıcı otomatik yükler</span>
            </button>
          </div>

          {mode === 'schedule' && (
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-[11px] font-medium text-[#828092]">Tarih ve saat</label>
                <input
                  type="datetime-local"
                  value={scheduledDate}
                  onChange={(e) => setScheduledDate(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg bg-white dark:bg-[#25293C] border border-slate-200 dark:border-slate-700 text-[#4B465C] dark:text-[#DBD7EC] focus:outline-none focus:ring-2 focus:ring-[#7367F0]/40 focus:border-[#7367F0]"
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-[#828092]">Saat dilimi</label>
                <select
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg bg-white dark:bg-[#25293C] border border-slate-200 dark:border-slate-700 text-[#4B465C] dark:text-[#DBD7EC] focus:outline-none focus:ring-2 focus:ring-[#7367F0]/40 focus:border-[#7367F0]"
                >
                  {!COMMON_TIMEZONES.includes(timezone) && <option value={timezone}>{timezone} (Yerel)</option>}
                  {COMMON_TIMEZONES.map((tz) => (
                    <option key={tz} value={tz}>{tz}</option>
                  ))}
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200 dark:border-slate-800">
          <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting} className="text-xs">
            Vazgeç
          </Button>
          <Button
            type="submit"
            disabled={isSubmitting || !channelId || isThumbnailUploading}
            className="bg-red-600 hover:bg-red-700 text-white text-xs gap-2"
          >
            {isSubmitting ? (
              <>
                <Spinner size="sm" />
                <span>{mode === 'schedule' ? 'Planlanıyor...' : 'Başlatılıyor...'}</span>
              </>
            ) : mode === 'schedule' ? (
              <>
                <Calendar className="w-4 h-4" />
                <span>Yayını Planla</span>
              </>
            ) : (
              <>
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
                </svg>
                <span>Yüklemeyi Başlat</span>
              </>
            )}
          </Button>
        </div>
      </form>
      )}
    </Modal>
  );
};
