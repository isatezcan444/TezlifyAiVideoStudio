export type ConnectionStatus = 'active' | 'expired' | 'requires_reauth' | 'revoked' | 'disconnected';

export interface PlatformChannel {
  id: string;
  platform: string;
  platform_connection_id: string;
  channel_external_id: string;
  channel_name: string;
  channel_handle: string;
  avatar_url: string;
  description: string;
  is_primary: boolean;
  is_enabled: boolean;
  subscriber_count: number;
  uploads_playlist_id: string;
  connected_at: string;
  updated_at: string;
}

export interface CapabilityStatus {
  capability: string;
  status: 'active' | 'scope_required' | 'api_not_enabled' | 'reauth_required' | 'unavailable' | string;
  granted: boolean;
  optional: boolean;
  required_scopes: string[];
}

export interface PlatformConnection {
  id: string;
  platform: string;
  account_external_id: string;
  account_display_name: string;
  connection_status: ConnectionStatus | string;
  granted_scopes: string[];
  capabilities: CapabilityStatus[];
  connected_at: string;
  last_refreshed_at: string;
  token_expires_at: string;
  token_expired: boolean;
  channels: PlatformChannel[];
  channel_count: number;
}

export interface ConnectionListResponse {
  items: PlatformConnection[];
  total: number;
}

export interface ChannelSelection {
  active_channel_id: string;
  default_platform: string;
  updated_at: string;
}

export interface SwitchableChannel extends PlatformChannel {
  account_display_name: string;
  connection_status: string;
}

export interface ChannelListResponse {
  items: SwitchableChannel[];
  total: number;
  selection: ChannelSelection;
}

export interface ChannelContextPayload {
  channel_id: string;
  platform: string;
  platform_connection_id: string;
  connection_status: string;
  external_channel_id: string;
  channel_name: string;
}

export interface GlobalDashboard {
  connected: boolean;
  platforms: Array<{
    platform: string;
    display_name: string;
    implemented: boolean;
    accounts: number;
    active_accounts: number;
    channels: number;
    publish_records: number;
    scheduled_records: number;
  }>;
  accounts: PlatformConnection[];
  selection: { active_channel_id: string | null; default_platform: string };
  totals: {
    accounts: number;
    channels: number;
    publish_records: number;
    scheduled_records: number;
    publish_status_counts: Record<string, number>;
    schedule_status_counts: Record<string, number>;
  };
  sources: Record<string, string>;
  notes: string[];
  unresolved_publish_records: number;
}
