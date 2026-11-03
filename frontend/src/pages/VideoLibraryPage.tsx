import React, { useState } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { MediaAsset } from '../types/media';
import { formatBytes, formatDuration, formatDate } from '../lib/utils';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import {
  Film,
  Search,
  LayoutGrid,
  List as ListIcon,
  Play,
  Trash2,
  Eye,
  Clock,
  HardDrive,
} from 'lucide-react';

interface VideoLibraryPageProps {
  videos: MediaAsset[];
  isLoading: boolean;
  onSelectVideo: (asset: MediaAsset) => void;
  onRequestDelete: (asset: MediaAsset) => void;
  onNavigateImport: () => void;
}

export const VideoLibraryPage: React.FC<VideoLibraryPageProps> = ({
  videos,
  isLoading,
  onSelectVideo,
  onRequestDelete,
  onNavigateImport,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  const filteredVideos = videos.filter((v) => {
    const q = searchQuery.toLowerCase();
    return (
      v.original_filename.toLowerCase().includes(q) ||
      (v.metadata?.video_codec && v.metadata.video_codec.toLowerCase().includes(q)) ||
      (v.metadata?.resolution_label && v.metadata.resolution_label.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6">
      {/* Search and Toolbar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-4 rounded-xl bg-white dark:bg-[#2F3349] border border-slate-200/80 dark:border-white/[0.08] shadow-xs">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Video adı veya çözünürlükle ara..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-xs rounded-lg vuexy-input bg-slate-50 dark:bg-white/[0.03] border-slate-200 dark:border-white/[0.08] text-slate-800 dark:text-white focus:bg-white dark:focus:bg-[#25293C]"
          />
        </div>

        <div className="flex items-center space-x-2 shrink-0">
          <div className="flex items-center p-1 rounded-lg bg-slate-100 dark:bg-white/[0.05] border border-slate-200 dark:border-white/[0.08]">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1.5 rounded-md transition-colors ${
                viewMode === 'grid'
                  ? 'bg-white dark:bg-[#2F3349] text-[#7367F0] shadow-xs'
                  : 'text-slate-400 hover:text-slate-700 dark:hover:text-white'
              }`}
              title="Grid Görünümü"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-1.5 rounded-md transition-colors ${
                viewMode === 'list'
                  ? 'bg-white dark:bg-[#2F3349] text-[#7367F0] shadow-xs'
                  : 'text-slate-400 hover:text-slate-700 dark:hover:text-white'
              }`}
              title="Liste Görünümü"
            >
              <ListIcon className="w-4 h-4" />
            </button>
          </div>

          <Button
            variant="default"
            size="sm"
            onClick={onNavigateImport}
            className="gap-1.5"
          >
            <span>Video Aktar</span>
          </Button>
        </div>
      </div>

      {/* Video Content */}
      {isLoading ? (
        <div className="py-20 text-center text-xs text-slate-400">Videolar taranıyor...</div>
      ) : videos.length === 0 ? (
        <EmptyState
          icon={Film}
          title="Henüz Video Bulunmuyor"
          description="Yerel kütüphaneniz henüz boş. Bilgisayarınızdan MP4, MOV veya WEBM formatında video aktararak başlayabilirsiniz."
          actionLabel="İlk Videoyu İçe Aktar"
          onAction={onNavigateImport}
        />
      ) : filteredVideos.length === 0 ? (
        <div className="py-16 text-center text-xs text-slate-400">
          "{searchQuery}" aramasıyla eşleşen video bulunamadı.
        </div>
      ) : viewMode === 'grid' ? (
        /* GRID VIEW */
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredVideos.map((asset) => (
            <Card
              key={asset.id}
              className="group overflow-hidden hover:shadow-lg transition-all border border-slate-200/80 dark:border-white/[0.08]"
            >
              {/* Thumbnail / Video Banner */}
              <div
                onClick={() => onSelectVideo(asset)}
                className="relative aspect-video bg-slate-900 overflow-hidden cursor-pointer flex items-center justify-center group/thumb"
              >
                <div className="w-12 h-12 rounded-full bg-white/20 backdrop-blur-md text-white flex items-center justify-center group-hover/thumb:scale-110 group-hover/thumb:bg-[#7367F0] transition-all duration-200 shadow-lg">
                  <Play className="w-5 h-5 ml-0.5" />
                </div>

                {/* Duration Badge */}
                <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded-md bg-black/80 backdrop-blur-xs text-[11px] font-bold text-white flex items-center space-x-1">
                  <Clock className="w-3 h-3 text-[#7367F0]" />
                  <span>{formatDuration(asset.metadata?.duration_seconds)}</span>
                </div>

                {/* Resolution Pill */}
                {asset.metadata?.resolution_label && (
                  <div className="absolute top-2 left-2 px-2 py-0.5 rounded-md bg-black/60 backdrop-blur-xs text-[10px] font-bold text-white">
                    {asset.metadata.resolution_label}
                  </div>
                )}
              </div>

              {/* Card Body */}
              <CardContent className="p-4 space-y-3">
                <div className="truncate">
                  <h3
                    onClick={() => onSelectVideo(asset)}
                    className="text-xs font-bold text-slate-800 dark:text-white truncate cursor-pointer hover:text-[#7367F0] transition-colors"
                    title={asset.original_filename}
                  >
                    {asset.original_filename}
                  </h3>
                  <div className="flex items-center space-x-2 text-[11px] text-slate-400 dark:text-[#7E7F96] mt-1">
                    <span className="flex items-center space-x-1">
                      <HardDrive className="w-3 h-3" />
                      <span>{formatBytes(asset.file_size_bytes)}</span>
                    </span>
                    <span>•</span>
                    <span>{asset.metadata?.fps ? `${asset.metadata.fps} fps` : '30 fps'}</span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-white/[0.06]">
                  <StatusBadge status={asset.status} />

                  <div className="flex items-center space-x-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => onSelectVideo(asset)}
                      title="Detay & Oynat"
                      className="h-7 w-7 text-slate-500 hover:text-[#7367F0]"
                    >
                      <Eye className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => onRequestDelete(asset)}
                      title="Sil"
                      className="h-7 w-7 text-slate-500 hover:text-[#EA5455]"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        /* LIST VIEW */
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-white/[0.02] border-b border-slate-200 dark:border-white/[0.08] text-slate-400 dark:text-[#7E7F96] uppercase text-[10px] font-bold">
                <tr>
                  <th className="py-3 px-4">Video</th>
                  <th className="py-3 px-4">Süre</th>
                  <th className="py-3 px-4">Çözünürlük</th>
                  <th className="py-3 px-4">Boyut</th>
                  <th className="py-3 px-4">Durum</th>
                  <th className="py-3 px-4">Eklenme</th>
                  <th className="py-3 px-4 text-right">İşlemler</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-white/[0.05]">
                {filteredVideos.map((asset) => (
                  <tr
                    key={asset.id}
                    className="hover:bg-slate-50 dark:hover:bg-white/[0.02] transition-colors"
                  >
                    <td className="py-3 px-4 font-semibold text-slate-800 dark:text-white max-w-xs truncate">
                      <div className="flex items-center space-x-2.5">
                        <Play
                          onClick={() => onSelectVideo(asset)}
                          className="w-4 h-4 text-[#7367F0] cursor-pointer shrink-0"
                        />
                        <span
                          onClick={() => onSelectVideo(asset)}
                          className="truncate cursor-pointer hover:underline"
                        >
                          {asset.original_filename}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-slate-600 dark:text-slate-300">
                      {formatDuration(asset.metadata?.duration_seconds)}
                    </td>
                    <td className="py-3 px-4 text-slate-600 dark:text-slate-300">
                      {asset.metadata?.resolution_label || 'Bilinmiyor'}
                    </td>
                    <td className="py-3 px-4 text-slate-600 dark:text-slate-300">
                      {formatBytes(asset.file_size_bytes)}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={asset.status} />
                    </td>
                    <td className="py-3 px-4 text-slate-400 dark:text-[#7E7F96]">
                      {formatDate(asset.created_at)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end space-x-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => onSelectVideo(asset)}
                          className="h-7 w-7 text-slate-500 hover:text-[#7367F0]"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => onRequestDelete(asset)}
                          className="h-7 w-7 text-slate-500 hover:text-[#EA5455]"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
};
