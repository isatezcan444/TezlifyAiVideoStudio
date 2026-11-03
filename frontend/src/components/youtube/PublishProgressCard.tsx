import React, { useState, useEffect } from 'react';
import { PublishRecord } from '../../types/publish';
import { PublishStatusBadge } from './PublishStatusBadge';
import { apiService } from '../../services/api';
import { Button } from '../ui/button';
import { Spinner } from '../ui/Spinner';

interface PublishProgressCardProps {
  initialRecord: PublishRecord;
  onRecordUpdated?: (record: PublishRecord) => void;
}

export const PublishProgressCard: React.FC<PublishProgressCardProps> = ({
  initialRecord,
  onRecordUpdated,
}) => {
  const [record, setRecord] = useState<PublishRecord>(initialRecord);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  // Poll status while job is active
  useEffect(() => {
    let interval: any = null;
    const isActive = ['pending', 'authenticating', 'uploading', 'processing'].includes(record.status);

    if (isActive) {
      interval = setInterval(async () => {
        try {
          const fresh = await apiService.getPublishRecord(record.id);
          setRecord(fresh);
          if (onRecordUpdated) onRecordUpdated(fresh);
          if (!['pending', 'authenticating', 'uploading', 'processing'].includes(fresh.status)) {
            clearInterval(interval);
          }
        } catch (err) {
          console.error('Error polling publish status:', err);
        }
      }, 1500);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [record.id, record.status, onRecordUpdated]);

  const handleResume = async () => {
    setIsActionLoading(true);
    try {
      const updated = await apiService.resumePublish(record.id);
      setRecord(updated);
      if (onRecordUpdated) onRecordUpdated(updated);
    } catch (err: any) {
      alert(`Yükleme devam ettirilemedi: ${err.message || 'Bilinmeyen hata'}`);
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!window.confirm('Bu YouTube yüklemesini iptal etmek istediğinize emin misiniz?')) {
      return;
    }
    setIsActionLoading(true);
    try {
      const updated = await apiService.cancelPublish(record.id);
      setRecord(updated);
      if (onRecordUpdated) onRecordUpdated(updated);
    } catch (err: any) {
      alert(`İptal edilemedi: ${err.message || 'Bilinmeyen hata'}`);
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleCopyLink = () => {
    if (record.external_video_url) {
      navigator.clipboard.writeText(record.external_video_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const formatMB = (bytes: number) => (bytes / (1024 * 1024)).toFixed(1);

  return (
    <div className="p-4 rounded-xl bg-white dark:bg-[#2F3349] border border-slate-200/80 dark:border-slate-800 shadow-sm space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className="text-sm font-semibold text-[#4B465C] dark:text-[#DBD7EC] truncate max-w-md">
              {record.title}
            </h4>
            <PublishStatusBadge status={record.status} />
          </div>
          <p className="text-xs text-[#828092] dark:text-[#908DA1] mt-0.5">
            Oluşturulma: {new Date(record.created_at).toLocaleString('tr-TR')}
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          {record.status === 'uploading' && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleCancel}
              disabled={isActionLoading}
              className="text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-50 border-rose-200"
            >
              İptal Et
            </Button>
          )}

          {record.status === 'paused' && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleResume}
                disabled={isActionLoading}
                className="text-xs text-[#7367F0] hover:bg-[#7367F0]/10 border-[#7367F0]/30"
              >
                {isActionLoading ? <Spinner size="sm" /> : 'Devam Ettir'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancel}
                disabled={isActionLoading}
                className="text-xs text-rose-600 hover:text-rose-700"
              >
                İptal Et
              </Button>
            </>
          )}

          {record.status === 'published' && record.external_video_url && (
            <div className="flex items-center gap-2">
              <a
                href={record.external_video_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-600 hover:bg-red-700 text-white shadow-sm transition-colors"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
                </svg>
                <span>YouTube'da Aç</span>
              </a>
              <button
                onClick={handleCopyLink}
                className="p-1.5 rounded-lg text-slate-500 hover:text-slate-700 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                title="Bağlantıyı Kopyala"
              >
                {copied ? (
                  <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">Kopyalandı!</span>
                ) : (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Progress Bar (Visible while uploading or processing or paused) */}
      {(['uploading', 'paused', 'processing', 'pending'].includes(record.status) || record.progress_percentage > 0) && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="text-[#828092] dark:text-[#908DA1]">
              {formatMB(record.uploaded_bytes)} MB / {formatMB(record.total_bytes)} MB
            </span>
            <span className="font-semibold text-[#7367F0]">
              %{record.progress_percentage}
            </span>
          </div>
          <div className="w-full bg-slate-100 dark:bg-slate-800 h-2.5 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 rounded-full ${
                record.status === 'published'
                  ? 'bg-emerald-500'
                  : record.status === 'paused'
                  ? 'bg-amber-500'
                  : record.status === 'failed'
                  ? 'bg-red-500'
                  : 'bg-gradient-to-r from-[#7367F0] to-[#9E95F5]'
              }`}
              style={{ width: `${record.progress_percentage}%` }}
            />
          </div>
        </div>
      )}

      {/* Error Message if failed */}
      {record.error_message && (
        <div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-600 dark:text-red-400">
          <strong>Hata ({record.error_code || 'Bilinmiyor'}):</strong> {record.error_message}
        </div>
      )}
    </div>
  );
};
