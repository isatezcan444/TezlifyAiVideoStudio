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
import {
  ChannelListResponse,
  ChannelSelection,
  ConnectionListResponse,
  GlobalDashboard,
} from '../types/account';

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

function withChannel(search: URLSearchParams, channelId?: string | null): URLSearchParams {
  if (channelId) search.set('channel_id', channelId);
  return search;
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

  // --- Connected accounts ---
  async listConnections(includeDisconnected = false): Promise<ConnectionListResponse> {
    const res = await fetch(
      `${API_BASE}/social/connections?include_disconnected=${includeDisconnected}`
    );
    if (!res.ok) throw await parseError(res, 'Bağlı hesaplar alınamadı.');
    return res.json();
  },

  async disconnectConnection(connectionId: string): Promise<{ success: boolean; selection: ChannelSelection }> {
    const res = await fetch(`${API_BASE}/social/connections/${connectionId}`, { method: 'DELETE' });
    if (!res.ok) throw await parseError(res, 'Hesap bağlantısı kesilemedi.');
    return res.json();
  },

  async reconnectConnection(connectionId: string): Promise<{ auth_url: string; state: string }> {
    const res = await fetch(`${API_BASE}/social/connections/${connectionId}/reconnect`, {
      method: 'POST',
    });
    if (!res.ok) throw await parseError(res, 'Yeniden bağlanma oturumu başlatılamadı.');
    return res.json();
  },

  async getYouTubeStatus(): Promise<YouTubeStatusResponse> {
    const res = await fetch(`${API_BASE}/social/youtube/status`);
    if (!res.ok) throw new ApiError('YouTube durumu alınamadı.', res.status);
    return res.json();
  },

  async connectYouTube(
    intent: 'add_account' | 'reconnect' = 'add_account',
    connectionId?: string
  ): Promise<{ auth_url: string; state: string }> {
    const search = new URLSearchParams({ intent });
    if (connectionId) search.set('connection_id', connectionId);
    const res = await fetch(`${API_BASE}/social/youtube/connect?${search.toString()}`, {
      method: 'POST',
    });
    if (!res.ok) throw await parseError(res, 'YouTube bağlantı oturumu başlatılamadı.');
    return res.json();
  },

  async disconnectYouTube(): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/social/youtube/disconnect`, { method: 'DELETE' });
    if (!res.ok) throw await parseError(res, 'YouTube bağlantısı kesilemedi.');
    return res.json();
  },

  // --- Channels & global selector ---
  async listChannels(params: {
    platform?: string;
    includeDisabled?: boolean;
    includeDisconnected?: boolean;
  } = {}): Promise<ChannelListResponse> {
    const search = new URLSearchParams();
    if (params.platform) search.set('platform', params.platform);
    if (params.includeDisabled) search.set('include_disabled', 'true');
    if (params.includeDisconnected) search.set('include_disconnected', 'true');
    const res = await fetch(`${API_BASE}/channels?${search.toString()}`);
    if (!res.ok) throw await parseError(res, 'Kanal listesi alınamadı.');
    return res.json();
  },

  async getChannelSelection(): Promise<ChannelSelection> {
    const res = await fetch(`${API_BASE}/channels/selection`);
    if (!res.ok) throw await parseError(res, 'Aktif kanal bilgisi alınamadı.');
    return res.json();
  },

  async selectChannel(channelId: string): Promise<ChannelSelection> {
    const res = await fetch(`${API_BASE}/channels/selection`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ channel_id: channelId }),
    });
    if (!res.ok) throw await parseError(res, 'Kanal seçilemedi.');
    return res.json();
  },

  async setChannelEnabled(channelId: string, enabled: boolean): Promise<{ updated: boolean }> {
    const res = await fetch(`${API_BASE}/channels/${channelId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
    if (!res.ok) throw await parseError(res, 'Kanal durumu güncellenemedi.');
    return res.json();
  },

  // --- Publishing ---
  async startPublish(req: StartPublishRequest): Promise<PublishRecord> {
    const res = await fetch(`${API_BASE}/social/youtube/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw await parseError(res, 'Yayınlama başlatılamadı.');
    return res.json();
  },

  async listPublishRecords(limit = 50, offset = 0, channelId?: string | null): Promise<PublishListResponse> {
    const search = withChannel(new URLSearchParams(), channelId);
    search.set('limit', String(limit));
    search.set('offset', String(offset));
    const res = await fetch(`${API_BASE}/social/youtube/publish?${search.toString()}`);
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

  async listSchedules(
    status?: ScheduleStatus,
    limit = 50,
    offset = 0,
    channelId?: string | null
  ): Promise<ScheduledPublishListResponse> {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (channelId) params.append('channel_id', channelId);
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());

    const res = await fetch(`${API_BASE}/scheduler?${params.toString()}`);
    if (!res.ok) throw new ApiError('Planlama listesi alınamadı.', res.status);
    return res.json();
  },

  async getUpcomingSchedules(limit = 20, channelId?: string | null): Promise<ScheduledPublish[]> {
    const params = withChannel(new URLSearchParams(), channelId);
    params.set('limit', String(limit));
    const res = await fetch(`${API_BASE}/scheduler/upcoming?${params.toString()}`);
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

  async getDashboard(range = '28', channelId?: string | null): Promise<DashboardSnapshot> {
    const params = withChannel(new URLSearchParams({ range }), channelId);
    const res = await fetch(`${API_BASE}/dashboard?${params.toString()}`);
    if (!res.ok) throw await parseError(res, 'Panel verisi alınamadı.');
    return res.json();
  },

  async getGlobalDashboard(): Promise<GlobalDashboard> {
    const res = await fetch(`${API_BASE}/dashboard/global`);
    if (!res.ok) throw await parseError(res, 'Genel panel verisi alınamadı.');
    return res.json();
  },

  async getChannelOverview(channelId?: string | null): Promise<ChannelOverviewResponse> {
    const params = withChannel(new URLSearchParams(), channelId);
    const res = await fetch(`${API_BASE}/channels/youtube/overview?${params.toString()}`);
    if (!res.ok) throw await parseError(res, 'Kanal bilgisi alınamadı.');
    return res.json();
  },

  async listChannelVideos(
    maxResults = 25,
    pageToken?: string,
    channelId?: string | null
  ): Promise<ChannelVideoListResponse> {
    const params = withChannel(new URLSearchParams({ max_results: String(maxResults) }), channelId);
    if (pageToken) params.set('page_token', pageToken);
    const res = await fetch(`${API_BASE}/channels/youtube/videos?${params.toString()}`);
    if (!res.ok) throw await parseError(res, 'Kanal videoları alınamadı.');
    return res.json();
  },

  async getChannelVideo(videoId: string, channelId?: string | null): Promise<{ video: ChannelVideo; source: string }> {
    const params = withChannel(new URLSearchParams(), channelId);
    const res = await fetch(`${API_BASE}/channels/youtube/videos/${videoId}?${params.toString()}`);
    if (!res.ok) throw await parseError(res, 'Video detayı alınamadı.');
    return res.json();
  },

  async updateChannelVideo(
    videoId: string,
    payload: VideoUpdatePayload,
    channelId?: string | null
  ): Promise<{ video: ChannelVideo; source: string }> {
    const params = withChannel(new URLSearchParams(), channelId);
    const res = await fetch(`${API_BASE}/channels/youtube/videos/${videoId}?${params.toString()}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await parseError(res, 'Video güncellenemedi.');
    return res.json();
  },

  async listChannelPlaylists(
    maxResults = 25,
    channelId?: string | null
  ): Promise<{ items: ChannelPlaylist[]; source: string }> {
    const params = withChannel(new URLSearchParams({ max_results: String(maxResults) }), channelId);
    const res = await fetch(`${API_BASE}/channels/youtube/playlists?${params.toString()}`);
    if (!res.ok) throw await parseError(res, 'Oynatma listeleri alınamadı.');
    return res.json();
  },

  async listVideoCategories(channelId?: string | null): Promise<{ items: VideoCategory[] }> {
    const params = withChannel(new URLSearchParams(), channelId);
    const res = await fetch(`${API_BASE}/channels/youtube/categories?${params.toString()}`);
    if (!res.ok) throw await parseError(res, 'Video kategorileri alınamadı.');
    return res.json();
  },

  async getChannelAnalytics(params: {
    range?: string;
    startDate?: string;
    endDate?: string;
    dimensions?: string[];
    includeRevenue?: boolean;
    channelId?: string | null;
  } = {}): Promise<AnalyticsResponse> {
    const search = withChannel(new URLSearchParams({ range: params.range || '28' }), params.channelId);
    if (params.startDate) search.set('start_date', params.startDate);
    if (params.endDate) search.set('end_date', params.endDate);
    if (params.dimensions?.length) search.set('dimensions', params.dimensions.join(','));
    if (params.includeRevenue) search.set('include_revenue', 'true');

    const res = await fetch(`${API_BASE}/channels/youtube/analytics?${search.toString()}`);
    if (!res.ok) throw await parseError(res, 'Analitik verisi alınamadı.');
    return res.json();
  },

  async listComments(params: {
    videoId?: string;
    maxResults?: number;
    pageToken?: string;
    channelId?: string | null;
  } = {}): Promise<CommentListResponse> {
    const search = withChannel(
      new URLSearchParams({ max_results: String(params.maxResults ?? 25) }),
      params.channelId
    );
    if (params.videoId) search.set('video_id', params.videoId);
    if (params.pageToken) search.set('page_token', params.pageToken);
    const res = await fetch(`${API_BASE}/comments?${search.toString()}`);
    if (!res.ok) throw await parseError(res, 'Yorumlar alınamadı.');
    return res.json();
  },

  async replyToComment(
    commentId: string,
    text: string,
    channelId?: string | null
  ): Promise<{ comment: VideoComment; source: string }> {
    const params = withChannel(new URLSearchParams(), channelId);
    const res = await fetch(`${API_BASE}/comments/${commentId}/reply?${params.toString()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw await parseError(res, 'Yanıt gönderilemedi.');
    return res.json();
  },

  async moderateComment(
    commentId: string,
    status: string,
    channelId?: string | null
  ): Promise<{ comment: VideoComment; source: string }> {
    const params = withChannel(new URLSearchParams(), channelId);
    const res = await fetch(`${API_BASE}/comments/${commentId}/moderation?${params.toString()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) throw await parseError(res, 'Yorum durumu değiştirilemedi.');
    return res.json();
  },
};
