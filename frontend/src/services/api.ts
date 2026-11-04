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
  Character,
  CharacterListResponse,
  StudioAsset,
  StudioAssetListResponse,
  RenderJob,
  RenderJobListResponse,
  StudioProject,
  StudioProjectListResponse,
  VoiceListResponse,
  VoiceStatusResponse,
  CompositionSummary,
  VideoComposition,
  GenerateStoryResponse,
  SceneGraph,
} from '../types/studio';

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

  // --- Character & Asset Studio (Stage 4.2) ---
  getCharacterThumbnailUrl(id: string): string {
    return `${API_BASE}/studio/characters/${id}/thumbnail`;
  },

  getAssetThumbnailUrl(id: string): string {
    return `${API_BASE}/studio/assets/${id}/thumbnail`;
  },

  async listCharacters(limit = 50, offset = 0): Promise<CharacterListResponse> {
    const res = await fetch(`${API_BASE}/studio/characters?limit=${limit}&offset=${offset}`);
    if (!res.ok) throw new ApiError('Karakterler yüklenemedi.', res.status);
    return res.json();
  },

  async getCharacter(id: string): Promise<Character> {
    const res = await fetch(`${API_BASE}/studio/characters/${id}`);
    if (!res.ok) throw new ApiError('Karakter bulunamadı.', res.status);
    return res.json();
  },

  async createCharacter(data: Partial<Character>): Promise<Character> {
    const res = await fetch(`${API_BASE}/studio/characters`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Karakter oluşturulamadı.', res.status, err.error_code);
    }
    return res.json();
  },

  async updateCharacter(id: string, data: Partial<Character>): Promise<Character> {
    const res = await fetch(`${API_BASE}/studio/characters/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Karakter güncellenemedi.', res.status, err.error_code);
    }
    return res.json();
  },

  async deleteCharacter(id: string): Promise<{ id: string; deleted: boolean }> {
    const res = await fetch(`${API_BASE}/studio/characters/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Karakter silinemedi.', res.status, err.error_code);
    }
    return res.json();
  },

  async listAssets(category?: string, limit = 100, offset = 0): Promise<StudioAssetListResponse> {
    const q = category ? `&category=${category}` : '';
    const res = await fetch(`${API_BASE}/studio/assets?limit=${limit}&offset=${offset}${q}`);
    if (!res.ok) throw new ApiError('Varlıklar yüklenemedi.', res.status);
    return res.json();
  },

  async getAsset(id: string): Promise<StudioAsset> {
    const res = await fetch(`${API_BASE}/studio/assets/${id}`);
    if (!res.ok) throw new ApiError('Varlık bulunamadı.', res.status);
    return res.json();
  },

  // --- Blender Headless Render Studio (Stage 4.3) ---
  getRenderVideoUrl(jobId: string): string {
    return `${API_BASE}/studio/renders/${jobId}/video`;
  },

  async startProjectRender(
    projectId: string,
    engineOverride?: string,
    synthesizeVoices?: boolean
  ): Promise<RenderJob> {
    const payload: Record<string, any> = {};
    if (engineOverride) payload.engine_override = engineOverride;
    if (synthesizeVoices !== undefined) payload.synthesize_voices = synthesizeVoices;

    const res = await fetch(`${API_BASE}/studio/projects/${projectId}/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Render işlemi başlatılamadı.', res.status, err.error_code);
    }
    return res.json();
  },

  async getRenderJob(jobId: string): Promise<RenderJob> {
    const res = await fetch(`${API_BASE}/studio/renders/${jobId}`);
    if (!res.ok) throw new ApiError('Render durumu alınamadı.', res.status);
    return res.json();
  },

  async listProjectRenders(projectId: string): Promise<RenderJobListResponse> {
    const res = await fetch(`${API_BASE}/studio/projects/${projectId}/renders`);
    if (!res.ok) throw new ApiError('Render geçmişi alınamadı.', res.status);
    return res.json();
  },

  async listRenderJobs(
    limit = 100,
    offset = 0,
    status?: RenderJob['status']
  ): Promise<RenderJobListResponse> {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    if (status) params.set('status', status);
    const res = await fetch(`${API_BASE}/studio/renders?${params.toString()}`);
    if (!res.ok) throw new ApiError('Studio render geçmişi alınamadı.', res.status);
    return res.json();
  },

  // --- Studio Projects (Stage 4.1 & 4.3) ---
  async listProjects(limit = 50, offset = 0): Promise<StudioProjectListResponse> {
    const res = await fetch(`${API_BASE}/studio/projects?limit=${limit}&offset=${offset}`);
    if (!res.ok) throw new ApiError('Projeler yüklenemedi.', res.status);
    return res.json();
  },

  async getProject(id: string): Promise<StudioProject> {
    const res = await fetch(`${API_BASE}/studio/projects/${id}`);
    if (!res.ok) throw new ApiError('Proje bulunamadı.', res.status);
    return res.json();
  },

  async createProject(data: { title: string; description?: string; scene_graph?: any }): Promise<StudioProject> {
    const res = await fetch(`${API_BASE}/studio/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Proje oluşturulamadı.', res.status, err.error_code);
    }
    return res.json();
  },

  async updateProject(
    id: string,
    data: {
      title?: string;
      description?: string;
      status?: string;
      scene_graph?: SceneGraph;
    }
  ): Promise<StudioProject> {
    const res = await fetch(`${API_BASE}/studio/projects/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Proje güncellenemedi.', res.status, err.error_code);
    }
    return res.json();
  },

  async deleteProject(id: string): Promise<{ id: string; deleted: boolean; archived: boolean }> {
    const res = await fetch(`${API_BASE}/studio/projects/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Proje silinemedi.', res.status, err.error_code);
    }
    return res.json();
  },

  async generateStory(data: {
    prompt: string;
    target_duration_seconds?: number;
    aspect_ratio?: string;
    genre?: string;
    provider?: string;
  }): Promise<GenerateStoryResponse> {
    const res = await fetch(`${API_BASE}/studio/generate-story`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Senaryo üretilemedi.', res.status, err.error_code);
    }
    return res.json();
  },

  // --- Voice Studio & ElevenLabs TTS (Stage 4.4) ---
  async listVoices(): Promise<VoiceListResponse> {
    const res = await fetch(`${API_BASE}/studio/voices`);
    if (!res.ok) throw new ApiError('Ses listesi alınamadı.', res.status);
    return res.json();
  },

  async getVoiceStatus(): Promise<VoiceStatusResponse> {
    const res = await fetch(`${API_BASE}/studio/voices/status`);
    if (!res.ok) throw new ApiError('Ses servis durumu alınamadı.', res.status);
    return res.json();
  },

  // --- Video Composition Studio (Stage 4.5) ---
  async getProjectComposition(projectId: string): Promise<CompositionSummary> {
    const res = await fetch(`${API_BASE}/studio/projects/${projectId}/composition`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Kompozisyon yüklenemedi.', res.status, err.error_code);
    }
    return res.json();
  },

  async saveProjectComposition(
    projectId: string,
    composition: VideoComposition
  ): Promise<CompositionSummary> {
    const res = await fetch(`${API_BASE}/studio/projects/${projectId}/composition`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ composition }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Kompozisyon kaydedilemedi.', res.status, err.error_code);
    }
    return res.json();
  },

  async startCompositionRender(
    projectId: string,
    composition: VideoComposition,
    options: { engineOverride?: string; synthesizeVoices?: boolean } = {}
  ): Promise<RenderJob> {
    const payload: Record<string, any> = { composition };
    if (options.engineOverride) payload.engine_override = options.engineOverride;
    if (options.synthesizeVoices !== undefined) payload.synthesize_voices = options.synthesizeVoices;

    const res = await fetch(`${API_BASE}/studio/projects/${projectId}/composition/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(err.detail || 'Kompozisyon render işlemi başlatılamadı.', res.status, err.error_code);
    }
    return res.json();
  },

  getRenderSubtitlesUrl(jobId: string): string {
    return `${API_BASE}/studio/renders/${jobId}/subtitles`;
  },
};


