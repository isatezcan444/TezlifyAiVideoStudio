import React, { useState } from 'react';
import { Modal } from '../ui/Modal';
import { MediaAsset } from '../../types/media';
import { formatBytes, formatDuration, formatDate } from '../../lib/utils';
import { StatusBadge } from '../ui/StatusBadge';
import { Button } from '../ui/button';
import { apiService } from '../../services/api';
import {
  Calendar,
  HardDrive,
  Copy,
  Check,
  Download,
  Trash2,
  Info,
} from 'lucide-react';

interface VideoDetailsModalProps {
  asset: MediaAsset | null;
  isOpen: boolean;
  onClose: () => void;
  onDeleteRequest: (asset: MediaAsset) => void;
  onPublishRequest?: (asset: MediaAsset) => void;
}

export const VideoDetailsModal: React.FC<VideoDetailsModalProps> = ({
  asset,
  isOpen,
  onClose,
  onDeleteRequest,
  onPublishRequest,
}) => {
  const [copiedHash, setCopiedHash] = useState(false);

  if (!asset) return null;

  const streamUrl = apiService.getStreamUrl(asset.id);
  const meta = asset.metadata;

  const handleCopyHash = () => {
    navigator.clipboard.writeText(asset.sha256_hash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={asset.original_filename}
      maxWidth="4xl"
    >
      <div className="space-y-6">
        {/* Video Player */}
        <div className="relative aspect-video rounded-xl overflow-hidden bg-black shadow-inner flex items-center justify-center">
          <video
            controls
            autoPlay={false}
            playsInline
            preload="metadata"
            className="w-full h-full object-contain"
            src={streamUrl}
          >
            Tarayıcınız HTML5 video etiketini desteklemiyor.
          </video>
        </div>

        {/* Status and Action Row */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl bg-slate-50 dark:bg-white/[0.03] border border-slate-200/60 dark:border-white/[0.08]">
          <div className="flex items-center space-x-3">
            <StatusBadge status={asset.status} />
            <span className="text-xs text-slate-500 dark:text-[#7E7F96]">
              {asset.mime_type}
            </span>
          </div>

          <div className="flex items-center space-x-2">
            {onPublishRequest && (
              <Button
                size="sm"
                onClick={() => {
                  onClose();
                  onPublishRequest(asset);
                }}
                className="bg-red-600 hover:bg-red-700 text-white gap-1.5 shadow-xs"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
                </svg>
                <span>YouTube'da Yayınla</span>
              </Button>
            )}
            <a href={streamUrl} download={asset.original_filename}>
              <Button variant="outline" size="sm" className="gap-1.5">
                <Download className="w-4 h-4" />
                <span>İndir</span>
              </Button>
            </a>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => onDeleteRequest(asset)}
              className="gap-1.5"
            >
              <Trash2 className="w-4 h-4" />
              <span>Sil</span>
            </Button>
          </div>
        </div>

        {/* Technical Metadata Grid */}
        <div>
          <div className="flex items-center space-x-2 mb-3">
            <Info className="w-4 h-4 text-[#7367F0]" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-200">
              Teknik Video Detayları
            </h4>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05]">
              <span className="text-slate-400 dark:text-[#7E7F96] block text-[11px]">Süre</span>
              <span className="font-bold text-slate-800 dark:text-white text-sm">
                {formatDuration(meta?.duration_seconds)}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05]">
              <span className="text-slate-400 dark:text-[#7E7F96] block text-[11px]">Çözünürlük</span>
              <span className="font-bold text-slate-800 dark:text-white text-sm">
                {meta?.resolution_label || 'Bilinmiyor'}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05]">
              <span className="text-slate-400 dark:text-[#7E7F96] block text-[11px]">En/Boy Oranı</span>
              <span className="font-bold text-slate-800 dark:text-white text-sm">
                {meta?.aspect_ratio || '16:9'}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05]">
              <span className="text-slate-400 dark:text-[#7E7F96] block text-[11px]">Kare Hızı (FPS)</span>
              <span className="font-bold text-slate-800 dark:text-white text-sm">
                {meta?.fps ? `${meta.fps} fps` : '30 fps'}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05]">
              <span className="text-slate-400 dark:text-[#7E7F96] block text-[11px]">Video Codec</span>
              <span className="font-bold text-slate-800 dark:text-white text-sm">
                {meta?.video_codec || 'Bilinmiyor'}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05]">
              <span className="text-slate-400 dark:text-[#7E7F96] block text-[11px]">Ses Codec</span>
              <span className="font-bold text-slate-800 dark:text-white text-sm">
                {meta?.audio_codec || 'Yok / Sessiz'}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05]">
              <span className="text-slate-400 dark:text-[#7E7F96] block text-[11px]">Dosya Boyutu</span>
              <span className="font-bold text-slate-800 dark:text-white text-sm">
                {formatBytes(asset.file_size_bytes)}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05]">
              <span className="text-slate-400 dark:text-[#7E7F96] block text-[11px]">Analiz Kaynağı</span>
              <span className="font-bold text-slate-800 dark:text-white text-sm capitalize">
                {meta?.probe_source || 'Sistem'}
              </span>
            </div>
          </div>
        </div>

        {/* SHA-256 Hash and Storage Info */}
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/[0.05] space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-slate-500 dark:text-[#7E7F96]">
              SHA-256 İçerik Özeti (Hash):
            </span>
            <button
              onClick={handleCopyHash}
              className="inline-flex items-center space-x-1 text-[#7367F0] hover:underline"
            >
              {copiedHash ? (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span>Kopyalandı</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Kopyala</span>
                </>
              )}
            </button>
          </div>
          <p className="font-mono text-[11px] text-slate-600 dark:text-slate-300 break-all select-all">
            {asset.sha256_hash}
          </p>
        </div>

        <div className="flex items-center justify-between text-xs text-slate-400 dark:text-[#7E7F96] pt-2 border-t border-slate-100 dark:border-white/[0.08]">
          <div className="flex items-center space-x-1.5">
            <Calendar className="w-3.5 h-3.5" />
            <span>Eklenme: {formatDate(asset.created_at)}</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <HardDrive className="w-3.5 h-3.5" />
            <span className="truncate max-w-xs">{asset.filename}</span>
          </div>
        </div>
      </div>
    </Modal>
  );
};
