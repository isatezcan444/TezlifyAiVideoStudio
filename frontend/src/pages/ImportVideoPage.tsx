import React, { useState, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/Progress';
import { apiService, ApiError } from '../services/api';
import { MediaAsset } from '../types/media';
import {
  UploadCloud,
  FileVideo,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
  Zap,
} from 'lucide-react';

interface ImportVideoPageProps {
  onUploadSuccess: (asset: MediaAsset) => void;
  onViewVideo: (asset: MediaAsset) => void;
}

const ALLOWED_EXTENSIONS = ['.mp4', '.mov', '.webm', '.mkv', '.m4v'];

export const ImportVideoPage: React.FC<ImportVideoPageProps> = ({
  onUploadSuccess,
  onViewVideo,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [duplicateWarning, setDuplicateWarning] = useState<{ id: string; message: string } | null>(null);
  const [uploadedAsset, setUploadedAsset] = useState<MediaAsset | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateAndUpload = async (file: File) => {
    setErrorMessage(null);
    setDuplicateWarning(null);
    setUploadedAsset(null);

    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setErrorMessage(
        `Geçersiz dosya uzantısı (${ext}). Yalnızca ${ALLOWED_EXTENSIONS.join(', ')} formatları desteklenir.`
      );
      return;
    }

    if (file.size > 500 * 1024 * 1024) {
      setErrorMessage('Dosya boyutu 500 MB sınırını aşıyor.');
      return;
    }

    setSelectedFile(file);
    setIsUploading(true);
    setProgress(0);

    try {
      const asset = await apiService.uploadVideo(file, (percent) => {
        setProgress(percent);
      });
      setUploadedAsset(asset);
      onUploadSuccess(asset);
    } catch (err: any) {
      if (err instanceof ApiError && err.statusCode === 409) {
        setDuplicateWarning({
          id: err.errorCode === 'DUPLICATE_MEDIA' ? 'existing' : '',
          message: err.message,
        });
      } else {
        setErrorMessage(err.message || 'Video yüklenirken beklenmeyen bir hata oluştu.');
      }
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndUpload(e.target.files[0]);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Manuel Video İçe Aktarma</CardTitle>
          <p className="text-xs text-slate-500 dark:text-[#7E7F96]">
            Bilgisayarınızdaki mevcut hazır videoları sisteme aktarın. Dosyalar yerel diskinizde güvenle saklanır, FFprobe ile analiz edilir ve kütüphanenize eklenir.
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Dropzone Area */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => !isUploading && fileInputRef.current?.click()}
            className={`relative p-10 sm:p-14 rounded-2xl border-2 border-dashed transition-all duration-200 flex flex-col items-center justify-center text-center cursor-pointer ${
              isDragging
                ? 'border-[#7367F0] bg-[#7367F0]/5 shadow-lg shadow-[#7367F0]/10 scale-[1.01]'
                : 'border-slate-300 dark:border-white/[0.12] hover:border-[#7367F0]/60 bg-slate-50/50 dark:bg-white/[0.01]'
            } ${isUploading ? 'pointer-events-none opacity-80' : ''}`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".mp4,.mov,.webm,.mkv,.m4v"
              onChange={handleFileChange}
              className="hidden"
            />

            <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-[#7367F0] to-[#9E95F5] text-white flex items-center justify-center shadow-lg shadow-[#7367F0]/30 mb-4">
              <UploadCloud className="w-8 h-8" />
            </div>

            <h3 className="text-base font-bold text-slate-800 dark:text-white mb-1">
              Videoyu buraya sürükleyip bırakın
            </h3>
            <p className="text-xs text-slate-500 dark:text-[#7E7F96] max-w-sm mb-4 leading-relaxed">
              veya bilgisayarınızdan dosya seçmek için tıklayın
            </p>

            <div className="flex flex-wrap items-center justify-center gap-1.5">
              {ALLOWED_EXTENSIONS.map((ext) => (
                <span
                  key={ext}
                  className="px-2 py-0.5 rounded bg-slate-200/60 dark:bg-white/[0.06] text-[10px] font-bold text-slate-600 dark:text-slate-300 uppercase"
                >
                  {ext.replace('.', '')}
                </span>
              ))}
              <span className="text-[10px] text-slate-400 dark:text-[#7E7F96] ml-2">
                (Maks. 500 MB)
              </span>
            </div>
          </div>

          {/* Upload Progress State */}
          {isUploading && (
            <div className="p-5 rounded-xl bg-slate-50 dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.08] space-y-3">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2 truncate">
                  <FileVideo className="w-4 h-4 text-[#7367F0] shrink-0" />
                  <span className="font-bold text-slate-800 dark:text-white truncate">
                    {selectedFile?.name}
                  </span>
                </div>
                <span className="font-extrabold text-[#7367F0] shrink-0">
                  %{progress}
                </span>
              </div>
              <Progress value={progress} />
              <p className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                Dosya diske aktarılıyor ve SHA-256 içerik özeti hesaplanıyor...
              </p>
            </div>
          )}

          {/* Success Banner */}
          {uploadedAsset && (
            <div className="p-5 rounded-xl bg-[#28C76F]/10 border border-[#28C76F]/30 text-slate-800 dark:text-white flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex items-center space-x-3">
                <div className="p-2 rounded-lg bg-[#28C76F] text-white shrink-0">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-[#28C76F]">
                    Video Başarıyla İçe Aktarıldı!
                  </h4>
                  <p className="text-xs text-slate-600 dark:text-slate-300">
                    {uploadedAsset.original_filename} kütüphaneye eklendi ve oynatmaya hazır.
                  </p>
                </div>
              </div>
              <Button
                variant="default"
                size="sm"
                onClick={() => onViewVideo(uploadedAsset)}
                className="gap-1.5 shrink-0"
              >
                <span>Önizle ve İncele</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          )}

          {/* Duplicate Warning */}
          {duplicateWarning && (
            <div className="p-5 rounded-xl bg-[#FF9F43]/10 border border-[#FF9F43]/30 text-slate-800 dark:text-white flex items-start space-x-3">
              <div className="p-2 rounded-lg bg-[#FF9F43] text-white shrink-0">
                <AlertCircle className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <h4 className="text-xs font-bold text-[#FF9F43]">
                  Aynı Video Zaten Kütüphanede Mevcut
                </h4>
                <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                  {duplicateWarning.message}
                </p>
              </div>
            </div>
          )}

          {/* General Error Message */}
          {errorMessage && (
            <div className="p-5 rounded-xl bg-[#EA5455]/10 border border-[#EA5455]/30 text-slate-800 dark:text-white flex items-start space-x-3">
              <div className="p-2 rounded-lg bg-[#EA5455] text-white shrink-0">
                <AlertCircle className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <h4 className="text-xs font-bold text-[#EA5455]">
                  Yükleme Başarısız Oldu
                </h4>
                <p className="text-xs text-slate-600 dark:text-slate-300">
                  {errorMessage}
                </p>
              </div>
            </div>
          )}

          {/* Technical Info Callout */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-4 border-t border-slate-100 dark:border-white/[0.08] text-xs">
            <div className="flex items-start space-x-2.5">
              <ShieldCheck className="w-4 h-4 text-[#28C76F] shrink-0 mt-0.5" />
              <div>
                <span className="font-bold block text-slate-800 dark:text-white">
                  SHA-256 Doğrulama
                </span>
                <span className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                  Aynı dosyanın mükerrer yüklenmesi anında engellenir.
                </span>
              </div>
            </div>

            <div className="flex items-start space-x-2.5">
              <Zap className="w-4 h-4 text-[#7367F0] shrink-0 mt-0.5" />
              <div>
                <span className="font-bold block text-slate-800 dark:text-white">
                  Chunked Streaming
                </span>
                <span className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                  Büyük video dosyaları RAM'i şişirmeden parça parça diske yazılır.
                </span>
              </div>
            </div>

            <div className="flex items-start space-x-2.5">
              <FileVideo className="w-4 h-4 text-[#00CFE8] shrink-0 mt-0.5" />
              <div>
                <span className="font-bold block text-slate-800 dark:text-white">
                  HTTP Range Desteği
                </span>
                <span className="text-[11px] text-slate-400 dark:text-[#7E7F96]">
                  Oynatıcıda video ileri-geri sarma işlemleri kesintisiz çalışır.
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
