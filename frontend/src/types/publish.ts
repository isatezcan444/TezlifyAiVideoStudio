export type SocialPlatform = 'youtube';

export type PrivacyStatus = 'public' | 'unlisted' | 'private';

export type PublishStatus =
  | 'pending'
  | 'authenticating'
  | 'uploading'
  | 'paused'
  | 'processing'
  | 'published'
  | 'failed'
  | 'cancelled'
  | 'requires_reauth';

export interface SocialAccount {
  id: string;
  platform: SocialPlatform;
  account_name: string;
  channel_id: string;
  channel_avatar_url?: string | null;
  is_active: boolean;
  token_expires_at?: string | null;
  is_expired: boolean;
}

export interface YouTubeStatusResponse {
  connected: boolean;
  account: SocialAccount | null;
}

export interface StartPublishRequest {
  media_asset_id: string;
  title: string;
  description?: string;
  tags?: string[];
  category_id?: string;
  privacy_status?: PrivacyStatus;
  thumbnail_path?: string | null;
}

export interface PublishRecord {
  id: string;
  media_asset_id: string;
  platform: SocialPlatform;
  external_video_id?: string | null;
  external_video_url?: string | null;
  title: string;
  description: string;
  tags: string[];
  category_id: string;
  privacy_status: PrivacyStatus;
  status: PublishStatus;
  progress_percentage: number;
  uploaded_bytes: number;
  total_bytes: number;
  upload_session_uri?: string | null;
  thumbnail_path?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  published_at?: string | null;
}

export interface PublishListResponse {
  items: PublishRecord[];
  total: number;
}
