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
import {
  AnalyticsResponse,
  ChannelOverviewResponse,
  ChannelPlaylist,
  ChannelVideo,
  ChannelVideoListResponse,
  CommentListResponse,
  DashboardSnapshot,
  PlatformDescriptor,
  VideoCategory,
  VideoComment,
  VideoUpdatePayload,
} from '../types/creator';

const API_BASE = '/api/v1';

export class ApiError extends Error {
  errorCode?: string;
  statusCode: number;
  payload?: Record<string, unknown>;

  constructor(message: string, statusCode: number, errorCode?: string, payload?: Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.errorCode = errorCode;
    this.payload = payload;
  }
}

async function parseError(res: Response, fallback: string): Promise<ApiError> {
  const err = await res.json().catch(() => ({}));
  return new ApiError(err.detail || fallback, res.status, err.error_code, err);
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

  // --- Local media library ---
  async listMedia(limit = 100, offset = 0): Promise<MediaListResponse> {
    const res = await fetch(`${API_BASE}/media?limit=${limit}&offset=${offset}`);
    if (!res.ok) throw new ApiError('Medya listesi yüklenemedi.', res.status);
    return res.json();
  },

  async getMedia(id: string): Promise<MediaAsset> {
    const res = await fetch(`${API_BASE}/media/${id}`);
    if (!res.ok) throw await parseError(res, 'Medya detayı bulunamadı.');
    return res.json();
  },

  async deleteMedia(id: string): Promise<{ success: boolean; id: string }> {
    const res = await fetch(`${API_BASE}/media/${id}`, { method: 'DELETE' });
    if (!res.ok) throw await parseError(res, 'Medya silinemedi.');
    return res.json();
  },

  uploadVideo(file: File, onProgress?: (percent: number) => void): Promise<MediaAsset> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append('file', file);

      xhr.open('POST', `${API_BASE}/media/upload`);

      if (onProgress && xhr.upload) {
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            onProgress(Math.round((e.loaded / e.total) * 100));
          }
        };
      }

      xhr.onload = () => {
        try {
          const response = JSON.parse(xhr.responseText || '{}');
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(response as MediaAsset);
          } else {
            reject(new ApiError(response.detail || 'Video yüklenirken hata oluştu.', xhr.status, response.error_code));
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

  // --- YouTube OAuth & publishing ---
  async getYouTubeStatus(): Promise<YouTubeStatusResponse> {
    const res = await fetch(`${API_BASE}/social/youtube/status`);
    if (!res.ok) throw new ApiError('YouTube durumu alınamadı.', res.status);
    return res.json();
  },

  async connectYouTube(): Promise<{ auth_url: string; state: string }> {
    const res = await fetch(`${API_BASE}/social/youtube/connect`, { method: 'POST' });
    if (!res.ok) throw await parseError(res, 'YouTube bağlantı oturumu başlatılamadı.');
    return res.json();
  },

  async disconnectYouTube(): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/social/youtube/disconnect`, { method: 'DELETE' });
    if (!res.ok) throw await parseError(res, 'YouTube bağlantısı kesilemedi.');
    return res.json();
  },

  async startPublish(req: StartPublishRequest): Promise<PublishRecord> {
    const res = await fetch(`${API_BASE}/social/youtube/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw await parseError(res, 'Yayınlama başlatılamadı.');
    return res.json();
  },

  async listPublishRecords(limit = 50, offset = 0): Promise<PublishListResponse> {
    const res = await fetch(`${API_BASE}/social/youtube/publish?limit=${limit}&offset=${offset}`);
    if (!res.ok) throw new ApiError('Yayın geçmişi yüklenemedi.', res.status);
    return res.json();
  },

  async getPublishRecord(publishId: string): Promise<PublishRecord> {
    const res = await fetch(`${API_BASE}/social/youtube/publish/${publishId}`);
    if (!res.ok) throw await parseError(res, 'Yayın durumu alınamadı.');
    return res.json();
  },

  async resumePublish(publishId: string): Promise<PublishRecord> {
    const res = await fetch(`${API_BASE}/social/youtube/publish/${publishId}/resume`, { method: 'POST' });
    if (!res.ok) throw await parseError(res, 'Yükleme devam ettirilemedi.');
    return res.json();
  },

  async cancelPublish(publishId: string): Promise<PublishRecord> {
    const res = await fetch(`${API_BASE}/social/youtube/publish/${publishId}/cancel`, { method: 'POST' });
    if (!res.ok) throw await parseError(res, 'Yükleme iptal edilemedi.');
    return res.json();
  },

  // --- Publishing schedule ---
  async createSchedule(payload: CreateScheduledPublishPayload): Promise<ScheduledPublish> {
    const res = await fetch(`${API_BASE}/scheduler`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await parseError(res, 'Yayın planlanamadı.');
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
    if (!res.ok) throw await parseError(res, 'Plan detayı bulunamadı.');
    return res.json();
  },

  async updateSchedule(scheduleId: string, payload: UpdateScheduledPublishPayload): Promise<ScheduledPublish> {
    const res = await fetch(`${API_BASE}/scheduler/${scheduleId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await parseError(res, 'Plan güncellenemedi.');
    return res.json();
  },

  async cancelSchedule(scheduleId: string): Promise<ScheduledPublish> {
    const res = await fetch(`${API_BASE}/scheduler/${scheduleId}/cancel`, { method: 'POST' });
    if (!res.ok) throw await parseError(res, 'Plan iptal edilemedi.');
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
    if (!res.ok) throw await parseError(res, 'Yayın tekrar denenemedi.');
    return res.json();
  },

  // --- Creator Studio: platforms, channel, analytics, comments ---
  async listPlatforms(): Promise<PlatformDescriptor[]> {
    const res = await fetch(`${API_BASE}/platforms`);
    if (!res.ok) throw new ApiError('Platform listesi alınamadı.', res.status);
    return res.json();
  },

  async getDashboard(range = '28'): Promise<DashboardSnapshot> {
    const res = await fetch(`${API_BASE}/dashboard?range=${encodeURIComponent(range)}`);
    if (!res.ok) throw await parseError(res, 'Panel verisi alınamadı.');
    return res.json();
  },

  async getChannelOverview(): Promise<ChannelOverviewResponse> {
    const res = await fetch(`${API_BASE}/channels/youtube/overview`);
    if (!res.ok) throw await parseError(res, 'Kanal bilgisi alınamadı.');
    return res.json();
  },

  async listChannelVideos(maxResults = 25, pageToken?: string): Promise<ChannelVideoListResponse> {
    const params = new URLSearchParams({ max_results: String(maxResults) });
    if (pageToken) params.set('page_token', pageToken);
    const res = await fetch(`${API_BASE}/channels/youtube/videos?${params.toString()}`);
    if (!res.ok) throw await parseError(res, 'Kanal videoları alınamadı.');
    return res.json();
  },

  async getChannelVideo(videoId: string): Promise<{ video: ChannelVideo; source: string }> {
    const res = await fetch(`${API_BASE}/channels/youtube/videos/${videoId}`);
    if (!res.ok) throw await parseError(res, 'Video detayı alınamadı.');
    return res.json();
  },

  async updateChannelVideo(videoId: string, payload: VideoUpdatePayload): Promise<{ video: ChannelVideo; source: string }> {
    const res = await fetch(`${API_BASE}/channels/youtube/videos/${videoId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await parseError(res, 'Video güncellenemedi.');
    return res.json();
  },

  async listChannelPlaylists(maxResults = 25): Promise<{ items: ChannelPlaylist[]; source: string }> {
    const res = await fetch(`${API_BASE}/channels/youtube/playlists?max_results=${maxResults}`);
    if (!res.ok) throw await parseError(res, 'Oynatma listeleri alınamadı.');
    return res.json();
  },

  async listVideoCategories(): Promise<{ items: VideoCategory[] }> {
    const res = await fetch(`${API_BASE}/channels/youtube/categories`);
    if (!res.ok) throw await parseError(res, 'Video kategorileri alınamadı.');
    return res.json();
  },

  async getChannelAnalytics(params: {
    range?: string;
    startDate?: string;
    endDate?: string;
    dimensions?: string[];
    includeRevenue?: boolean;
  } = {}): Promise<AnalyticsResponse> {
    const search = new URLSearchParams({ range: params.range || '28' });
    if (params.startDate) search.set('start_date', params.startDate);
    if (params.endDate) search.set('end_date', params.endDate);
    if (params.dimensions?.length) search.set('dimensions', params.dimensions.join(','));
    if (params.includeRevenue) search.set('include_revenue', 'true');

    const res = await fetch(`${API_BASE}/channels/youtube/analytics?${search.toString()}`);
    if (!res.ok) throw await parseError(res, 'Analitik verisi alınamadı.');
    return res.json();
  },

  async listComments(params: { videoId?: string; maxResults?: number; pageToken?: string } = {}): Promise<CommentListResponse> {
    const search = new URLSearchParams({ max_results: String(params.maxResults ?? 25) });
    if (params.videoId) search.set('video_id', params.videoId);
    if (params.pageToken) search.set('page_token', params.pageToken);
    const res = await fetch(`${API_BASE}/comments?${search.toString()}`);
    if (!res.ok) throw await parseError(res, 'Yorumlar alınamadı.');
    return res.json();
  },

  async replyToComment(commentId: string, text: string): Promise<{ comment: VideoComment; source: string }> {
    const res = await fetch(`${API_BASE}/comments/${commentId}/reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw await parseError(res, 'Yanıt gönderilemedi.');
    return res.json();
  },

  async moderateComment(commentId: string, status: string): Promise<{ comment: VideoComment; source: string }> {
    const res = await fetch(`${API_BASE}/comments/${commentId}/moderation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) throw await parseError(res, 'Yorum durumu değiştirilemedi.');
    return res.json();
  },
};
