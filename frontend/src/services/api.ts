import { MediaAsset, MediaListResponse, SystemStatus } from '../types/media';

const API_BASE = '/api/v1';

export class ApiError extends Error {
  errorCode?: string;
  statusCode: number;

  constructor(message: string, statusCode: number, errorCode?: string) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.errorCode = errorCode;
  }
}

export const apiService = {
  async getHealth(): Promise<{ status: string; app: string; version: string }> {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new ApiError('Sağlık kontrolü başarısız oldu.', res.status);
    return res.json();
  },

  async getSystemStatus(): Promise<SystemStatus> {
    const res = await fetch(`${API_BASE}/system/status`);
    if (!res.ok) throw new ApiError('Sistem durumu alınamadı.', res.status);
    return res.json();
  },

  async listMedia(limit = 100, offset = 0): Promise<MediaListResponse> {
    const res = await fetch(`${API_BASE}/media?limit=${limit}&offset=${offset}`);
    if (!res.ok) throw new ApiError('Medya listesi yüklenemedi.', res.status);
    return res.json();
  },

  async getMedia(id: string): Promise<MediaAsset> {
    const res = await fetch(`${API_BASE}/media/${id}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Medya detayı bulunamadı.', res.status, err.error_code);
    }
    return res.json();
  },

  async deleteMedia(id: string): Promise<{ success: boolean; id: string }> {
    const res = await fetch(`${API_BASE}/media/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Medya silinemedi.', res.status, err.error_code);
    }
    return res.json();
  },

  uploadVideo(
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<MediaAsset> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append('file', file);

      xhr.open('POST', `${API_BASE}/media/upload`);

      if (onProgress && xhr.upload) {
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            onProgress(percent);
          }
        };
      }

      xhr.onload = () => {
        try {
          const response = JSON.parse(xhr.responseText || '{}');
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(response as MediaAsset);
          } else {
            const detail = response.detail || 'Video yüklenirken hata oluştu.';
            reject(new ApiError(detail, xhr.status, response.error_code));
          }
        } catch {
          reject(new ApiError('Sunucu cevabı işlenemedi.', xhr.status));
        }
      };

      xhr.onerror = () => {
        reject(new ApiError('Sunucuya bağlanılamadı. Backend servisinin çalıştığından emin olun.', 0));
      };

      xhr.send(formData);
    });
  },

  getStreamUrl(mediaId: string): string {
    return `${API_BASE}/media/${mediaId}/stream`;
  },

  getThumbnailUrl(mediaId: string): string {
    return `${API_BASE}/media/${mediaId}/thumbnail`;
  },
};

