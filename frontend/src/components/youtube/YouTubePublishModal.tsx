import React, { useState, useEffect } from 'react';
import { MediaAsset } from '../../types/media';
import { PrivacyStatus, PublishRecord } from '../../types/publish';
import { apiService } from '../../services/api';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/button';
import { Spinner } from '../ui/Spinner';

interface YouTubePublishModalProps {
  asset: MediaAsset | null;
  isOpen: boolean;
  onClose: () => void;
  onPublishStarted: (record: PublishRecord) => void;
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

export const YouTubePublishModal: React.FC<YouTubePublishModalProps> = ({
  asset,
  isOpen,
  onClose,
  onPublishStarted,
}) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [categoryId, setCategoryId] = useState('22');
  const [privacyStatus, setPrivacyStatus] = useState<PrivacyStatus>('private');

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (asset) {
      // Default title without file extension
      const defaultTitle = asset.original_filename.replace(/\.[^/.]+$/, '');
      setTitle(defaultTitle.slice(0, 100));
      setDescription(`Tezlify AI Video Studio ile hazırlandı.\n\nDosya: ${asset.original_filename}`);
      setTagsInput('tezlify, animation, ai video');
      setCategoryId('22');
      setPrivacyStatus('private');
      setError(null);
    }
  }, [asset]);

  if (!asset) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError('Lütfen bir video başlığı girin.');
      return;
    }

    const tags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    setError(null);
    setIsSubmitting(true);

    try {
      const record = await apiService.startPublish({
        media_asset_id: asset.id,
        title: title.trim(),
        description: description.trim(),
        tags,
        category_id: categoryId,
        privacy_status: privacyStatus,
        thumbnail_path: asset.thumbnail_path,
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

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="YouTube'da Yayınla"
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-600 dark:text-rose-400">
            {error}
          </div>
        )}

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
              {asset.metadata?.resolution_label && (
                <span>• {asset.metadata.resolution_label}</span>
              )}
              {asset.metadata?.duration_seconds && (
                <span>• {Math.round(asset.metadata.duration_seconds)}s</span>
              )}
            </div>
          </div>
        </div>

        {/* Title Input */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-medium text-[#4B465C] dark:text-[#DBD7EC]">
              Video Başlığı *
            </label>
            <span className="text-[11px] text-[#828092] dark:text-[#908DA1]">
              {title.length}/100
            </span>
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
            <label className="text-xs font-medium text-[#4B465C] dark:text-[#DBD7EC]">
              Açıklama (Description)
            </label>
            <span className="text-[11px] text-[#828092] dark:text-[#908DA1]">
              {description.length}/5000
            </span>
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
            placeholder="ör. animasyon, 2d, blender, hikaye"
            className="w-full px-3 py-2 text-sm rounded-lg bg-white dark:bg-[#25293C] border border-slate-200 dark:border-slate-700 text-[#4B465C] dark:text-[#DBD7EC] focus:outline-none focus:ring-2 focus:ring-[#7367F0]/40 focus:border-[#7367F0]"
          />
        </div>

        {/* Category & Privacy Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-[#4B465C] dark:text-[#DBD7EC] mb-1">
              Kategori
            </label>
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
            <label className="block text-xs font-medium text-[#4B465C] dark:text-[#DBD7EC] mb-1">
              Gizlilik Durumu
            </label>
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

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200 dark:border-slate-800">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={isSubmitting}
            className="text-xs"
          >
            Vazgeç
          </Button>
          <Button
            type="submit"
            disabled={isSubmitting}
            className="bg-red-600 hover:bg-red-700 text-white text-xs gap-2"
          >
            {isSubmitting ? (
              <>
                <Spinner size="sm" />
                <span>Başlatılıyor...</span>
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
    </Modal>
  );
};
