export type PlatformId = 'youtube';

export interface PlatformDescriptor {
  id: string;
  display_name: string;
  implemented: boolean;
  capabilities: Record<string, boolean>;
}

export interface ChannelProfile {
  channel_id: string;
  title: string;
  description: string;
  avatar_url?: string | null;
  custom_url?: string | null;
  country?: string | null;
  published_at?: string | null;
  subscriber_count?: number | null;
  video_count?: number | null;
  view_count?: number | null;
  hidden_subscriber_count: boolean;
  uploads_playlist_id?: string | null;
}

export interface ChannelVideo {
  video_id: string;
  title: string;
  description: string;
  published_at?: string | null;
  thumbnail_url?: string | null;
  privacy_status?: string | null;
  upload_status?: string | null;
  duration_seconds?: number | null;
  view_count?: number | null;
  like_count?: number | null;
  comment_count?: number | null;
  tags: string[];
  category_id?: string | null;
}

export interface ChannelPlaylist {
  playlist_id: string;
  title: string;
  description: string;
  item_count?: number | null;
  published_at?: string | null;
}

export interface ChannelVideoListResponse {
  items: ChannelVideo[];
  next_page_token?: string | null;
  source: string;
}

export interface ChannelOverviewResponse {
  channel: ChannelProfile;
  playlists: ChannelPlaylist[];
  source: string;
}

export interface AnalyticsRow {
  dimensions: Record<string, string>;
  metrics: Record<string, number>;
}

export interface AnalyticsResult {
  available: boolean;
  source: string;
  reason?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  metrics: string[];
  dimensions: string[];
  totals: Record<string, number>;
  rows: AnalyticsRow[];
  revenue?: Record<string, unknown> | null;
  fetched_at: string;
}

export interface AnalyticsResponse {
  range: { key: string; start_date: string; end_date: string; days: number };
  analytics: AnalyticsResult;
  source: string | null;
  explanation: string | null;
  metric_notes: Record<string, string>;
}

export interface VideoComment {
  comment_id: string;
  video_id: string;
  author: string;
  text: string;
  like_count: number;
  published_at?: string | null;
  updated_at?: string | null;
  total_reply_count: number;
  moderation_status?: string | null;
}

export interface CommentListResponse {
  items: VideoComment[];
  next_page_token?: string | null;
  source: string;
}

export type DashboardSourceKey =
  | 'subscribers'
  | 'total_views'
  | 'video_count'
  | 'views_over_time'
  | 'subscriber_growth'
  | 'recent_uploads'
  | 'scheduled_uploads'
  | 'publish_history'
  | 'channel_status';

export interface DashboardPublishRecord {
  id: string;
  title: string;
  status: string;
  privacy_status: string;
  external_video_id?: string | null;
  published_at?: string | null;
  created_at: string;
}

export interface DashboardUpcoming {
  id: string;
  title: string;
  scheduled_at_utc: string;
  timezone: string;
  status: string;
  privacy_status: string;
}

export interface DashboardSnapshot {
  connected: boolean;
  range_days: number;
  channel: ChannelProfile | null;
  analytics: AnalyticsResult | null;
  recent_videos: ChannelVideo[];
  local_counts: {
    total_publish_records?: number;
    publish_status_counts?: Record<string, number>;
    upcoming_schedule_count?: number;
    account?: {
      id: string;
      account_name: string;
      channel_id: string;
      channel_avatar_url?: string | null;
      is_token_expired: boolean;
    };
  };
  upcoming_schedules: DashboardUpcoming[];
  recent_publishes: DashboardPublishRecord[];
  sources: Record<string, string>;
  warnings: string[];
  last_updated: string;
}

export interface VideoUpdatePayload {
  title?: string;
  description?: string;
  tags?: string[];
  category_id?: string;
  privacy_status?: string;
}

export interface VideoCategory {
  id: string;
  title: string;
}
