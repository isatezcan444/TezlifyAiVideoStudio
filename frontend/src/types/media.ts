export interface VideoMetadata {
  duration_seconds?: number | null;
  width?: number | null;
  height?: number | null;
  fps?: number | null;
  video_codec?: string | null;
  audio_codec?: string | null;
  aspect_ratio?: string | null;
  probe_source: string;
  resolution_label: string;
}

export interface MediaAsset {
  id: string;
  filename: string;
  original_filename: string;
  file_path: string;
  file_size_bytes: number;
  mime_type: string;
  sha256_hash: string;
  status: 'ready' | 'processing' | 'failed' | 'pending';
  thumbnail_path?: string | null;
  created_at: string;
  updated_at: string;
  metadata?: VideoMetadata | null;
}

export interface MediaListResponse {
  items: MediaAsset[];
  total: number;
}

export interface SystemStatus {
  status: string;
  app_name: string;
  version: string;
  os_name: string;
  python_version: string;
  ffmpeg_installed: boolean;
  ffprobe_installed: boolean;
  data_dir: string;
  disk_total_gb: number;
  disk_free_gb: number;
  total_videos: number;
  total_storage_bytes: number;
}

