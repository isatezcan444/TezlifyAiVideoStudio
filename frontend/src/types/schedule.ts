import { PrivacyStatus, SocialPlatform } from './publish';

export type ScheduleStatus =
  | 'scheduled'
  | 'processing'
  | 'published'
  | 'failed'
  | 'paused'
  | 'cancelled'
  | 'missed';

export interface ScheduledPublish {
  id: string;
  media_asset_id: string;
  social_account_id: string;
  platform: SocialPlatform | string;
  title: string;
  description: string;
  tags: string[];
  privacy_status: PrivacyStatus;
  scheduled_at_utc: string;
  timezone: string;
  status: ScheduleStatus;
  publish_record_id?: string | null;
  attempt_count: number;
  max_attempts: number;
  last_error_code?: string | null;
  last_error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface CreateScheduledPublishPayload {
  media_asset_id: string;
  title: string;
  description?: string;
  tags?: string[];
  privacy_status: PrivacyStatus;
  scheduled_at: string;
  timezone: string;
  max_attempts?: number;
}

export interface UpdateScheduledPublishPayload {
  title?: string;
  description?: string;
  tags?: string[];
  privacy_status?: PrivacyStatus;
  scheduled_at?: string;
  timezone?: string;
}

export interface ScheduledPublishListResponse {
  items: ScheduledPublish[];
  total: number;
}

export interface SchedulerStatusResponse {
  is_running: boolean;
  check_interval_seconds: number;
  last_tick_at: string | null;
  active_count: number;
  upcoming_count: number;
  failed_count: number;
  missed_count: number;
  published_count: number;
}
