import React, { useState, useEffect } from 'react';
import { MediaAsset } from '../../types/media';
import { PrivacyStatus } from '../../types/publish';
import { ScheduledPublish } from '../../types/schedule';
import { apiService } from '../../services/api';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/button';
import { Spinner } from '../ui/Spinner';
import { Calendar, Info } from 'lucide-react';

interface ScheduleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (scheduled: ScheduledPublish) => void;
  initialAsset?: MediaAsset | null;
  availableAssets?: MediaAsset[];
  editingSchedule?: ScheduledPublish | null;
}

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

export const ScheduleModal: React.FC<ScheduleModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  initialAsset = null,
  availableAssets = [],
  editingSchedule = null,
}) => {
  const [selectedAssetId, setSelectedAssetId] = useState<string>('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [privacyStatus, setPrivacyStatus] = useState<PrivacyStatus>('private');
  const [scheduledDate, setScheduledDate] = useState('');
  const [timezone, setTimezone] = useState('Europe/Istanbul');
  const [maxAttempts, setMaxAttempts] = useState(3);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Auto-detect user's local timezone
  useEffect(() => {
    try {
      const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (userTz) {
        setTimezone(userTz);
      }
    } catch {
      setTimezone('Europe/Istanbul');
    }
  }, []);

  // Format a Date object to YYYY-MM-DDTHH:MM for datetime-local
  const formatForDateTimeLocal = (date: Date) => {
    const pad = (n: number) => n.toString().padStart(2, '0');
    const y = date.getFullYear();
    const m = pad(date.getMonth() + 1);
    const d = pad(date.getDate());
    const h = pad(date.getHours());
    const min = pad(date.getMinutes());
    return `${y}-${m}-${d}T${h}:${min}`;
  };

  useEffect(() => {
    if (!isOpen) return;

    if (editingSchedule) {
      // Editing mode
      setSelectedAssetId(editingSchedule.media_asset_id);
      setTitle(editingSchedule.title);
      setDescription(editingSchedule.description);
      setTagsInput((editingSchedule.tags || []).join(', '));
      setPrivacyStatus(editingSchedule.privacy_status);
      setTimezone(editingSchedule.timezone || 'Europe/Istanbul');
      setMaxAttempts(editingSchedule.max_attempts || 3);

      const d = new Date(editingSchedule.scheduled_at_utc);
      setScheduledDate(formatForDateTimeLocal(d));
      setError(null);
    } else {
      // New Schedule mode
      const asset = initialAsset || (availableAssets.length > 0 ? availableAssets[0] : null);
      if (asset) {
        setSelectedAssetId(asset.id);
        const defaultTitle = asset.original_filename.replace(/\.[^/.]+$/, '');
        setTitle(defaultTitle.slice(0, 100));
        setDescription(`Tezlify AI Video Studio ile hazırlandı.\n\nDosya: ${asset.original_filename}`);
        setTagsInput('tezlify, youtube, scheduled video');
      } else {
        setSelectedAssetId('');
        setTitle('');
        setDescription('');
        setTagsInput('');
      }

      setPrivacyStatus('private');
      setMaxAttempts(3);

      // Default: 2 hours from now rounded to next 15-minute slot
      const nextTime = new Date(Date.now() + 2 * 60 * 60 * 1000);
      nextTime.setMinutes(Math.ceil(nextTime.getMinutes() / 15) * 15, 0, 0);
      setScheduledDate(formatForDateTimeLocal(nextTime));
      setError(null);
    }
  }, [isOpen, editingSchedule, initialAsset, availableAssets]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedAssetId && !editingSchedule) {
      setError('Lütfen yayınlanacak bir video seçin.');
      return;
    }
    if (!title.trim()) {
      setError('Lütfen bir video başlığı girin.');
      return;
    }
    if (!scheduledDate) {
      setError('Lütfen geçerli bir yayın tarihi ve saati seçin.');
      return;
    }

    // Convert local datetime input to ISO 8601 with timezone offset
    const dateObj = new Date(scheduledDate);
    if (isNaN(dateObj.getTime())) {
      setError('Tarih biçimi geçersiz.');
      return;
    }

    if (dateObj.getTime() <= Date.now()) {
      setError('Yayın tarihi ileri bir zaman olmalıdır.');
      return;
    }

    const isoString = dateObj.toISOString();

    const tags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    setError(null);
    setIsSubmitting(true);

    try {
      if (editingSchedule) {
        const updated = await apiService.updateSchedule(editingSchedule.id, {
          title: title.trim(),
          description: description.trim(),
          tags,
          privacy_status: privacyStatus,
          scheduled_at: isoString,
          timezone,
        });
        onSuccess(updated);
      } else {
        const created = await apiService.createSchedule({
          media_asset_id: selectedAssetId,
          title: title.trim(),
          description: description.trim(),
          tags,
          privacy_status: privacyStatus,
          scheduled_at: isoString,
          timezone,
          max_attempts: maxAttempts,
        });
        onSuccess(created);
      }
      onClose();
    } catch (err: any) {
      setError(err.message || 'Yayın planlanırken bir hata oluştu.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={editingSchedule ? 'Yayın Planını Düzenle' : 'YouTube Yayını Planla'}
      maxWidth="xl"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-600 dark:text-red-400 text-sm flex items-start gap-2">
            <Info className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Video Selection (if creating) */}
        {!editingSchedule && (
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
              Yayınlanacak Video <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <select
                value={selectedAssetId}
                onChange={(e) => {
                  setSelectedAssetId(e.target.value);
                  const found = availableAssets.find((a) => a.id === e.target.value);
                  if (found) {
                    const cleanTitle = found.original_filename.replace(/\.[^/.]+$/, '');
                    setTitle(cleanTitle.slice(0, 100));
                  }
                }}
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-white/[0.08] bg-slate-50 dark:bg-white/[0.04] text-slate-800 dark:text-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#7367F0]/40 transition-colors"
                required
              >
                <option value="" disabled>
                  Video seçin...
                </option>
                {availableAssets.map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.original_filename} ({(asset.file_size_bytes / (1024 * 1024)).toFixed(1)} MB)
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {/* Title */}
        <div>
          <div className="flex justify-between items-center mb-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Video Başlığı <span className="text-red-500">*</span>
            </label>
            <span className="text-xs text-slate-400">{title.length}/100</span>
          </div>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={100}
            placeholder="Örn: 2026 Antik Roma Belgeseli #1"
            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-white/[0.08] bg-slate-50 dark:bg-white/[0.04] text-slate-800 dark:text-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#7367F0]/40 transition-colors"
            required
          />
        </div>

        {/* Date, Time & Timezone Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
              Yayın Tarihi ve Saati <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <input
                type="datetime-local"
                value={scheduledDate}
                onChange={(e) => setScheduledDate(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-white/[0.08] bg-slate-50 dark:bg-white/[0.04] text-slate-800 dark:text-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#7367F0]/40 transition-colors"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
              Saat Dilimi (Timezone)
            </label>
            <div className="relative">
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-white/[0.08] bg-slate-50 dark:bg-white/[0.04] text-slate-800 dark:text-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#7367F0]/40 transition-colors"
              >
                {!COMMON_TIMEZONES.includes(timezone) && (
                  <option value={timezone}>{timezone} (Yerel)</option>
                )}
                {COMMON_TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>
                    {tz}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Privacy Status */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
            Gizlilik Seviyesi
          </label>
          <div className="grid grid-cols-3 gap-2">
            {[
              { id: 'private', label: 'Gizli (Önerilen)', desc: 'Yalnızca siz' },
              { id: 'unlisted', label: 'Liste Dışı', desc: 'Bağlantısı olanlar' },
              { id: 'public', label: 'Herkese Açık', desc: 'Tüm YouTube' },
            ].map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setPrivacyStatus(p.id as PrivacyStatus)}
                className={`p-3 rounded-xl border text-left transition-all ${
                  privacyStatus === p.id
                    ? 'border-[#7367F0] bg-[#7367F0]/10 text-[#7367F0] ring-1 ring-[#7367F0]'
                    : 'border-slate-200 dark:border-white/[0.08] hover:border-slate-300 dark:hover:border-white/[0.15]'
                }`}
              >
                <div className="text-xs font-semibold">{p.label}</div>
                <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{p.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Description */}
        <div>
          <div className="flex justify-between items-center mb-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Açıklama
            </label>
            <span className="text-xs text-slate-400">{description.length}/5000</span>
          </div>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            maxLength={5000}
            placeholder="Video hakkında açıklama ve bağlantılar..."
            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-white/[0.08] bg-slate-50 dark:bg-white/[0.04] text-slate-800 dark:text-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#7367F0]/40 transition-colors"
          />
        </div>

        {/* Tags */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
            Etiketler (Virgülle ayırın)
          </label>
          <input
            type="text"
            value={tagsInput}
            onChange={(e) => setTagsInput(e.target.value)}
            placeholder="örnek, animasyon, youtube"
            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-white/[0.08] bg-slate-50 dark:bg-white/[0.04] text-slate-800 dark:text-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#7367F0]/40 transition-colors"
          />
        </div>

        {/* Info Box */}
        <div className="bg-indigo-500/5 dark:bg-indigo-500/10 border border-indigo-500/15 rounded-xl p-3 flex items-start gap-2 text-xs text-indigo-700 dark:text-indigo-300">
          <Calendar className="w-4 h-4 shrink-0 mt-0.5" />
          <span>
            Zamanlayıcı belirlenen vakit geldiğinde videonuzu otomatik olarak YouTube kanalınıza yükleyecektir. Bilgisayar kapalı olsa bile uygulama yeniden açıldığında görev güvenle telafi edilir.
          </span>
        </div>

        {/* Modal Actions */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100 dark:border-white/[0.08]">
          <Button type="button" variant="ghost" onClick={onClose} disabled={isSubmitting}>
            Vazgeç
          </Button>
          <Button
            type="submit"
            disabled={isSubmitting}
            className="bg-[#7367F0] hover:bg-[#685dd8] text-white flex items-center gap-2"
          >
            {isSubmitting ? (
              <>
                <Spinner size="sm" />
                <span>Kaydediliyor...</span>
              </>
            ) : (
              <span>{editingSchedule ? 'Değişiklikleri Kaydet' : 'Yayını Planla'}</span>
            )}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
