import { MediaAsset, MediaListResponse, SystemStatus } from '../types/media';
import {
  YouTubeStatusResponse,
  StartPublishRequest,
  PublishRecord,
  PublishListResponse,
} from '../types/publish';
import {
  ScheduledPublish,
  ScheduledPublishListResponse,
  SchedulerStatusResponse,
  CreateScheduledPublishPayload,
  UpdateScheduledPublishPayload,
  ScheduleStatus,
} from '../types/schedule';

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

  // YouTube Publisher API
  async getYouTubeStatus(): Promise<YouTubeStatusResponse> {
    const res = await fetch(`${API_BASE}/social/youtube/status`);
    if (!res.ok) throw new ApiError('YouTube durumu alınamadı.', res.status);
    return res.json();
  },

  async connectYouTube(): Promise<{ auth_url: string; state: string }> {
    const res = await fetch(`${API_BASE}/social/youtube/connect`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'YouTube bağlantı oturumu başlatılamadı.', res.status, err.error_code);
    }
    return res.json();
  },

  async disconnectYouTube(): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/social/youtube/disconnect`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'YouTube bağlantısı kesilemedi.', res.status, err.error_code);
    }
    return res.json();
  },

  async startPublish(req: StartPublishRequest): Promise<PublishRecord> {
    const res = await fetch(`${API_BASE}/social/youtube/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Yayınlama başlatılamadı.', res.status, err.error_code);
    }
    return res.json();
  },

  async listPublishRecords(limit = 50, offset = 0): Promise<PublishListResponse> {
    const res = await fetch(`${API_BASE}/social/youtube/publish?limit=${limit}&offset=${offset}`);
    if (!res.ok) throw new ApiError('Yayın geçmişi yüklenemedi.', res.status);
    return res.json();
  },

  async getPublishRecord(publishId: string): Promise<PublishRecord> {
    const res = await fetch(`${API_BASE}/social/youtube/publish/${publishId}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Yayın durumu alınamadı.', res.status, err.error_code);
    }
    return res.json();
  },

  async resumePublish(publishId: string): Promise<PublishRecord> {
    const res = await fetch(`${API_BASE}/social/youtube/publish/${publishId}/resume`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Yükleme devam ettirilemedi.', res.status, err.error_code);
    }
    return res.json();
  },

  async cancelPublish(publishId: string): Promise<PublishRecord> {
    const res = await fetch(`${API_BASE}/social/youtube/publish/${publishId}/cancel`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Yükleme iptal edilemedi.', res.status, err.error_code);
    }
    return res.json();
  },

  // Publishing Schedule & Automatic Scheduler API (Stage 3)
  async createSchedule(payload: CreateScheduledPublishPayload): Promise<ScheduledPublish> {
    const res = await fetch(`${API_BASE}/scheduler`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Yayın planlanamadı.', res.status, err.error_code);
    }
    return res.json();
  },

  async listSchedules(status?: ScheduleStatus, limit = 50, offset = 0): Promise<ScheduledPublishListResponse> {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());

    const res = await fetch(`${API_BASE}/scheduler?${params.toString()}`);
    if (!res.ok) throw new ApiError('Planlama listesi alınamadı.', res.status);
    return res.json();
  },

  async getUpcomingSchedules(limit = 20): Promise<ScheduledPublish[]> {
    const res = await fetch(`${API_BASE}/scheduler/upcoming?limit=${limit}`);
    if (!res.ok) throw new ApiError('Yaklaşan yayınlar alınamadı.', res.status);
    return res.json();
  },

  async getSchedulerStatus(): Promise<SchedulerStatusResponse> {
    const res = await fetch(`${API_BASE}/scheduler/status`);
    if (!res.ok) throw new ApiError('Scheduler durumu alınamadı.', res.status);
    return res.json();
  },

  async getSchedule(scheduleId: string): Promise<ScheduledPublish> {
    const res = await fetch(`${API_BASE}/scheduler/${scheduleId}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Plan detayı bulunamadı.', res.status, err.error_code);
    }
    return res.json();
  },

  async updateSchedule(scheduleId: string, payload: UpdateScheduledPublishPayload): Promise<ScheduledPublish> {
    const res = await fetch(`${API_BASE}/scheduler/${scheduleId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Plan güncellenemedi.', res.status, err.error_code);
    }
    return res.json();
  },

  async cancelSchedule(scheduleId: string): Promise<ScheduledPublish> {
    const res = await fetch(`${API_BASE}/scheduler/${scheduleId}/cancel`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Plan iptal edilemedi.', res.status, err.error_code);
    }
    return res.json();
  },

  async retrySchedule(scheduleId: string, scheduledAt?: string, timezone?: string): Promise<ScheduledPublish> {
    const payload: { scheduled_at?: string; timezone?: string } = {};
    if (scheduledAt) payload.scheduled_at = scheduledAt;
    if (timezone) payload.timezone = timezone;

    const res = await fetch(`${API_BASE}/scheduler/${scheduleId}/retry`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Yayın tekrar denenemedi.', res.status, err.error_code);
    }
    return res.json();
  },
};

