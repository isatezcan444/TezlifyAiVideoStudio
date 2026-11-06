import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AnalyticsPage } from './AnalyticsPage';
import { CommentsPage } from './CommentsPage';
import { ConnectedAccountsPage } from './ConnectedAccountsPage';
import { PlatformSettingsPage } from './PlatformSettingsPage';
import { UploadVideoPage } from './UploadVideoPage';
import { apiService } from '../services/api';
import type { AnalyticsResponse, VideoComment } from '../types/creator';
import type { CapabilityStatus, PlatformConnection } from '../types/account';
import type { CapabilityName } from '../lib/capabilities';

const mockContext = {
  connections: [] as PlatformConnection[],
  channels: [] as any[],
  activeChannel: null as any,
  selection: null,
  isLoading: false,
  error: null,
  hasChannels: true,
  refresh: vi.fn(),
  selectChannel: vi.fn(),
};

vi.mock('../context/ChannelContext', () => ({
  useChannelContext: () => mockContext,
}));

vi.mock('../services/api', () => ({
  apiService: {
    listConnections: vi.fn(),
    listPlatforms: vi.fn(),
    listPublishRecords: vi.fn(),
    getChannelAnalytics: vi.fn(),
    listChannelVideos: vi.fn(),
    listComments: vi.fn(),
    replyToComment: vi.fn(),
    moderateComment: vi.fn(),
    grantCapabilities: vi.fn(),
    resumePublish: vi.fn(),
    disconnectConnection: vi.fn(),
  },
}));

const api = apiService as unknown as {
  listConnections: ReturnType<typeof vi.fn>;
  listPlatforms: ReturnType<typeof vi.fn>;
  listPublishRecords: ReturnType<typeof vi.fn>;
  getChannelAnalytics: ReturnType<typeof vi.fn>;
  listChannelVideos: ReturnType<typeof vi.fn>;
  listComments: ReturnType<typeof vi.fn>;
  replyToComment: ReturnType<typeof vi.fn>;
  moderateComment: ReturnType<typeof vi.fn>;
  grantCapabilities: ReturnType<typeof vi.fn>;
  disconnectConnection: ReturnType<typeof vi.fn>;
};

const CAPABILITIES: CapabilityName[] = [
  'identity',
  'channel_read',
  'analytics',
  'upload',
  'comments',
  'revenue',
];

function capabilityStatuses(
  overrides: Partial<Record<CapabilityName, CapabilityStatus['status']>> = {}
): CapabilityStatus[] {
  return CAPABILITIES.map((name) => {
    const status =
      overrides[name] ??
      (name === 'identity' || name === 'channel_read' ? 'active' : 'scope_required');
    return {
      capability: name,
      status,
      granted: status === 'active',
      optional: name === 'revenue',
      required_scopes: [],
    };
  });
}

function makeConnection(
  overrides: Partial<Record<CapabilityName, CapabilityStatus['status']>> = {}
): PlatformConnection {
  return {
    id: 'conn_1',
    platform: 'youtube',
    account_external_id: 'google:sub-1',
    account_display_name: 'Test Hesap',
    connection_status: 'active',
    granted_scopes: [],
    capabilities: capabilityStatuses(overrides),
    connected_at: '2026-11-01T10:00:00',
    last_refreshed_at: '',
    token_expires_at: '',
    token_expired: false,
    channels: [
      {
        id: 'ch_1',
        platform: 'youtube',
        platform_connection_id: 'conn_1',
        channel_external_id: 'UC_ONE',
        channel_name: 'Kanal Bir',
        channel_handle: '@kanalbir',
        avatar_url: '',
        description: '',
        is_primary: true,
        is_enabled: true,
        subscriber_count: 1200,
        uploads_playlist_id: '',
        connected_at: '',
        updated_at: '',
      },
    ],
    channel_count: 1,
  };
}

const activeChannel = {
  ...makeConnection().channels[0],
  account_display_name: 'Test Hesap',
  connection_status: 'active',
};

function finishOAuth(success: boolean) {
  act(() => {
    window.dispatchEvent(
      new MessageEvent('message', {
        data: { type: 'TEZLIFY_YOUTUBE_CONNECTED', success },
      })
    );
  });
}

function analyticsResponse(reason: string | null, explanation: string): AnalyticsResponse {
  return {
    range: { key: '7', start_date: '2026-10-30', end_date: '2026-11-05', days: 7 },
    analytics: {
      available: false,
      source: '',
      reason,
      start_date: '2026-10-30',
      end_date: '2026-11-05',
      metrics: [],
      dimensions: ['day'],
      totals: {},
      rows: [],
      revenue: null,
      fetched_at: '2026-11-05T00:00:00',
    },
    source: null,
    explanation,
    metric_notes: {},
  };
}

const comment: VideoComment = {
  comment_id: 'c_1',
  video_id: 'v_1',
  author: 'İzleyici',
  text: 'Harika video',
  like_count: 3,
  published_at: '2026-11-01T10:00:00',
  total_reply_count: 0,
  moderation_status: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockContext.connections = [];
  mockContext.activeChannel = null;
  mockContext.refresh.mockResolvedValue(undefined);
  window.localStorage.clear();
  vi.spyOn(window, 'open').mockReturnValue(null);
  api.listConnections.mockResolvedValue({ items: [], total: 0 });
  api.listPlatforms.mockResolvedValue([]);
  api.listPublishRecords.mockResolvedValue({ items: [], total: 0 });
  api.listChannelVideos.mockResolvedValue({ items: [], source: 'youtube' });
  api.listComments.mockResolvedValue({ items: [comment], source: 'youtube' });
  api.grantCapabilities.mockResolvedValue({
    auth_url: 'https://accounts.google.test/auth',
    state: 'state',
    capabilities: [],
  });
  api.disconnectConnection.mockResolvedValue({ success: true });
});

describe('ConnectedAccountsPage capability grid', () => {
  it('renders one status per capability and offers an incremental grant', async () => {
    const user = userEvent.setup();
    const connection = makeConnection();
    mockContext.connections = [connection];
    api.listConnections.mockResolvedValue({ items: [connection], total: 1 });

    render(<ConnectedAccountsPage />);

    expect(await screen.findByText('Video yükleme')).toBeInTheDocument();
    expect(screen.getAllByText('izin gerekli').length).toBeGreaterThan(0);
    expect(screen.getByText('aktif')).toBeInTheDocument();

    await user.click(screen.getAllByRole('button', { name: 'YouTube yükleme izni ver' })[0]);
    await waitFor(() =>
      expect(api.grantCapabilities).toHaveBeenCalledWith('conn_1', ['upload'])
    );
    expect(window.open).toHaveBeenCalledWith(
      'https://accounts.google.test/auth',
      expect.stringContaining('tezlify_grant_conn_1_upload'),
      expect.any(String)
    );

    finishOAuth(true);
    await waitFor(() => expect(mockContext.refresh).toHaveBeenCalled());
  });

  it('explains api_not_enabled without offering a grant button', async () => {
    const connection = makeConnection({ analytics: 'api_not_enabled' });
    mockContext.connections = [connection];
    api.listConnections.mockResolvedValue({ items: [connection], total: 1 });

    render(<ConnectedAccountsPage />);

    expect(await screen.findByText(/Google Cloud Console'da YouTube Analytics API etkin değil/i)).toBeInTheDocument();
    expect(screen.getByText('API kapalı')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Analytics izni ver' })
    ).not.toBeInTheDocument();
  });

  it('keeps the connection message when the grant is cancelled', async () => {
    const user = userEvent.setup();
    const connection = makeConnection();
    mockContext.connections = [connection];
    api.listConnections.mockResolvedValue({ items: [connection], total: 1 });

    render(<ConnectedAccountsPage />);
    await user.click(
      (await screen.findAllByRole('button', { name: 'YouTube yükleme izni ver' }))[0]
    );
    await waitFor(() => expect(api.grantCapabilities).toHaveBeenCalled());
    finishOAuth(false);

    expect(
      await screen.findByText(/Mevcut hesap bağlantınız ve izinleri korunuyor/)
    ).toBeInTheDocument();
  });
});

describe('UploadVideoPage permission gate', () => {
  it('blocks upload entry and explains the missing permission', async () => {
    const user = userEvent.setup();
    const connection = makeConnection();
    mockContext.connections = [connection];
    mockContext.activeChannel = activeChannel;

    render(
      <UploadVideoPage
        videos={[]}
        onNavigateLibrary={vi.fn()}
        onNavigateAccounts={vi.fn()}
      />
    );

    expect(await screen.findByText('YouTube yükleme izni gerekiyor')).toBeInTheDocument();
    expect(screen.queryByText('Yerel videoyu bu kanala yükle')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'YouTube yükleme izni ver' }));
    await waitFor(() =>
      expect(api.grantCapabilities).toHaveBeenCalledWith('conn_1', ['upload'])
    );
  });

  it('keeps the selected channel when the incremental grant is cancelled', async () => {
    const user = userEvent.setup();
    const connection = makeConnection();
    mockContext.connections = [connection];
    mockContext.activeChannel = activeChannel;
    window.localStorage.setItem('tezlify.active_channel_id', 'ch_1');

    render(
      <UploadVideoPage
        videos={[]}
        onNavigateLibrary={vi.fn()}
        onNavigateAccounts={vi.fn()}
      />
    );
    await user.click(
      await screen.findByRole('button', { name: 'YouTube yükleme izni ver' })
    );
    await waitFor(() => expect(api.grantCapabilities).toHaveBeenCalled());
    finishOAuth(false);

    expect(
      await screen.findByText(/Mevcut hesap bağlantınız korunuyor/)
    ).toBeInTheDocument();
    expect(mockContext.selectChannel).not.toHaveBeenCalled();
    expect(window.localStorage.getItem('tezlify.active_channel_id')).toBe('ch_1');
  });

  it('shows the upload entry when the capability is active', async () => {
    const connection = makeConnection({ upload: 'active' });
    mockContext.connections = [connection];
    mockContext.activeChannel = activeChannel;

    render(
      <UploadVideoPage
        videos={[]}
        onNavigateLibrary={vi.fn()}
        onNavigateAccounts={vi.fn()}
      />
    );

    expect(await screen.findByText('Yerel videoyu bu kanala yükle')).toBeInTheDocument();
    expect(screen.queryByText('YouTube yükleme izni gerekiyor')).not.toBeInTheDocument();
  });
});

describe('AnalyticsPage permission states', () => {
  it('offers an Analytics grant when the scope is missing', async () => {
    const user = userEvent.setup();
    const connection = makeConnection();
    mockContext.connections = [connection];
    mockContext.activeChannel = activeChannel;
    api.getChannelAnalytics.mockResolvedValue(
      analyticsResponse(
        'insufficient_scope',
        'Mevcut YouTube bağlantısı analiz iznini (yt-analytics.readonly) içermiyor.'
      )
    );

    render(<AnalyticsPage onNavigate={vi.fn()} />);

    expect(await screen.findByText('Analytics izni gerekiyor')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Analytics izni ver' }));
    await waitFor(() =>
      expect(api.grantCapabilities).toHaveBeenCalledWith('conn_1', ['analytics'])
    );
  });

  it('shows Google Cloud guidance instead of a grant button when the API is disabled', async () => {
    const connection = makeConnection({ analytics: 'api_not_enabled' });
    mockContext.connections = [connection];
    mockContext.activeChannel = activeChannel;
    api.getChannelAnalytics.mockResolvedValue(
      analyticsResponse(
        'api_not_enabled',
        "YouTube Analytics API bu Google Cloud projesinde etkin değil. Google Cloud Console üzerinden API'yi etkinleştirmeniz gerekir."
      )
    );

    render(<AnalyticsPage onNavigate={vi.fn()} />);

    expect(await screen.findByText('YouTube Analytics API etkin değil')).toBeInTheDocument();
    expect(screen.getByText(/Google Cloud Console/)).toBeInTheDocument();
    expect(screen.getByText(/Analytics · API kapalı/)).toBeInTheDocument();
    expect(screen.queryByText(/api_not_enabled/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Analytics izni ver' })
    ).not.toBeInTheDocument();
  });

  it('offers an optional revenue grant when the monetization scope is missing', async () => {
    const user = userEvent.setup();
    const connection = makeConnection({ analytics: 'active' });
    mockContext.connections = [connection];
    mockContext.activeChannel = activeChannel;
    api.getChannelAnalytics.mockResolvedValue({
      range: { key: '7', start_date: '2026-10-30', end_date: '2026-11-05', days: 7 },
      analytics: {
        available: true,
        source: 'youtube_analytics',
        reason: null,
        start_date: '2026-10-30',
        end_date: '2026-11-05',
        metrics: ['views'],
        dimensions: ['day'],
        totals: { views: 10 },
        rows: [{ dimensions: { day: '2026-10-30' }, metrics: { views: 10 } }],
        revenue: null,
        fetched_at: '2026-11-05T00:00:00',
      },
      source: 'youtube_analytics',
      explanation: null,
      metric_notes: {},
    });

    render(<AnalyticsPage onNavigate={vi.fn()} />);

    await user.click(await screen.findByLabelText('Gelir verisi iste'));
    const grantButton = await screen.findByRole('button', { name: 'Gelir izni ekle' });
    expect(screen.getByText(/Gelir verisi · izin gerekli/)).toBeInTheDocument();

    await user.click(grantButton);
    await waitFor(() =>
      expect(api.grantCapabilities).toHaveBeenCalledWith('conn_1', ['revenue'])
    );
  });

  it('hides the revenue grant and explains the missing data when the scope is active', async () => {
    const user = userEvent.setup();
    const connection = makeConnection({ analytics: 'active', revenue: 'active' });
    mockContext.connections = [connection];
    mockContext.activeChannel = activeChannel;
    api.getChannelAnalytics.mockResolvedValue({
      range: { key: '7', start_date: '2026-10-30', end_date: '2026-11-05', days: 7 },
      analytics: {
        available: true,
        source: 'youtube_analytics',
        reason: null,
        start_date: '2026-10-30',
        end_date: '2026-11-05',
        metrics: ['views'],
        dimensions: ['day'],
        totals: { views: 10 },
        rows: [],
        revenue: null,
        fetched_at: '2026-11-05T00:00:00',
      },
      source: 'youtube_analytics',
      explanation: null,
      metric_notes: {},
    });

    render(<AnalyticsPage onNavigate={vi.fn()} />);

    await user.click(await screen.findByLabelText('Gelir verisi iste'));

    expect(
      await screen.findByText(/Gelir verisi döndürülmedi/)
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Gelir izni ekle' })
    ).not.toBeInTheDocument();
  });

  it('renders revenue totals, daily trend and per-video revenue with titles', async () => {
    const user = userEvent.setup();
    const connection = makeConnection({ analytics: 'active', revenue: 'active' });
    mockContext.connections = [connection];
    mockContext.activeChannel = activeChannel;
    api.listChannelVideos.mockResolvedValue({
      items: [
        {
          video_id: 'vid_1',
          title: 'İlk Video',
          description: '',
          tags: [],
          thumbnail_url: 'https://img.test/thumb.jpg',
        },
      ],
      source: 'youtube_data_api',
    });
    api.getChannelAnalytics.mockResolvedValue({
      range: { key: '7', start_date: '2026-10-30', end_date: '2026-11-05', days: 7 },
      analytics: {
        available: true,
        source: 'youtube_analytics',
        reason: null,
        start_date: '2026-10-30',
        end_date: '2026-11-05',
        metrics: ['views'],
        dimensions: ['day'],
        totals: { views: 10 },
        rows: [],
        revenue: {
          available: true,
          amount: 1.5,
          ad_revenue: 1.2,
          currency: 'USD',
          daily: [
            {
              dimensions: { day: '2026-10-30' },
              metrics: { estimatedRevenue: 1.0, estimatedAdRevenue: 0.8 },
            },
            {
              dimensions: { day: '2026-10-31' },
              metrics: { estimatedRevenue: 0.5, estimatedAdRevenue: 0.4 },
            },
          ],
          top_videos: [
            {
              dimensions: { video: 'vid_1' },
              metrics: { estimatedRevenue: 1.5, estimatedAdRevenue: 1.2, views: 100 },
            },
          ],
          note: 'YouTube Analytics tahmini geliri; varsayılan para birimi USD.',
        },
        fetched_at: '2026-11-05T00:00:00',
      },
      source: 'youtube_analytics',
      explanation: null,
      metric_notes: {},
    });

    render(<AnalyticsPage onNavigate={vi.fn()} />);

    await user.click(await screen.findByLabelText('Gelir verisi iste'));

    expect(await screen.findByText('İlk Video')).toBeInTheDocument();
    expect(screen.getByText('Toplam tahmini gelir')).toBeInTheDocument();
    expect(screen.getByText('Reklam geliri')).toBeInTheDocument();
    expect(screen.getAllByText(/1,50/).length).toBeGreaterThan(0);
    expect(
      screen.getByText(/varsayılan para birimi USD/)
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'İlk Video' })
    ).toHaveAttribute('href', 'https://www.youtube.com/watch?v=vid_1');
  });
});

describe('CommentsPage write permission', () => {
  it('disables replies and moderation and offers the comments grant', async () => {
    const user = userEvent.setup();
    const connection = makeConnection();
    mockContext.connections = [connection];
    mockContext.activeChannel = activeChannel;

    render(<CommentsPage />);

    expect(await screen.findByText('Yorum yönetimi izni gerekiyor')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Yanıtla/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /İncelemeye al/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Reddet' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Yorum yönetimi izni ver' }));
    await waitFor(() =>
      expect(api.grantCapabilities).toHaveBeenCalledWith('conn_1', ['comments'])
    );
    expect(api.replyToComment).not.toHaveBeenCalled();
    expect(api.moderateComment).not.toHaveBeenCalled();
  });

  it('enables write actions when the comments capability is active', async () => {
    const connection = makeConnection({ comments: 'active' });
    mockContext.connections = [connection];
    mockContext.activeChannel = activeChannel;

    render(<CommentsPage />);

    expect(await screen.findByText('Harika video')).toBeInTheDocument();
    expect(screen.queryByText('Yorum yönetimi izni gerekiyor')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Yanıtla/ })).toBeEnabled();
  });
});

describe('PlatformSettingsPage capability presentation', () => {
  it('uses localized labels for every capability and hides unknown technical keys', async () => {
    api.listPlatforms.mockResolvedValue([
      {
        id: 'youtube',
        display_name: 'YouTube',
        implemented: true,
        capabilities: {
          connect_oauth: true,
          disconnect: true,
          list_accounts: true,
          list_channels: true,
          get_channel_profile: true,
          list_videos: true,
          upload_video: true,
          update_video: true,
          get_analytics: false,
          read_comments: true,
          write_comments: true,
          schedule_publish: true,
          monetization_revenue: false,
          mystery_capability: false,
        },
      },
    ]);

    render(<PlatformSettingsPage />);

    expect(await screen.findByText('Kanal profili')).toBeInTheDocument();
    expect(screen.getByText('Video güncelleme')).toBeInTheDocument();
    expect(screen.getByText('Planlı yayın')).toBeInTheDocument();
    expect(screen.getByText('Tanımsız yetenek')).toBeInTheDocument();
    expect(screen.queryByText('get_channel_profile')).not.toBeInTheDocument();
    expect(screen.queryByText('mystery_capability')).not.toBeInTheDocument();
  });

  it('never shows Analytics as open when the connection reports api_not_enabled', async () => {
    api.listPlatforms.mockResolvedValue([
      {
        id: 'youtube',
        display_name: 'YouTube',
        implemented: true,
        capabilities: { get_analytics: true },
      },
    ]);
    const connection = makeConnection({ analytics: 'api_not_enabled' });
    api.listConnections.mockResolvedValue({ items: [connection], total: 1 });

    render(<PlatformSettingsPage />);

    expect(await screen.findByText('API kapalı')).toBeInTheDocument();
    expect(screen.getByText(/Google Cloud Console/)).toBeInTheDocument();
    expect(screen.getByText('adaptör desteği var')).toBeInTheDocument();
    expect(screen.queryByText('Açık')).not.toBeInTheDocument();
    expect(screen.queryByText('Adaptör destekliyor')).not.toBeInTheDocument();
  });

  it('does not copy the connection Analytics state onto unimplemented platforms', async () => {
    api.listPlatforms.mockResolvedValue([
      {
        id: 'youtube',
        display_name: 'YouTube',
        implemented: true,
        capabilities: { get_analytics: true },
      },
      {
        id: 'instagram',
        display_name: 'Instagram',
        implemented: false,
        capabilities: { get_analytics: false },
      },
    ]);
    const connection = makeConnection({ analytics: 'api_not_enabled' });
    api.listConnections.mockResolvedValue({ items: [connection], total: 1 });

    render(<PlatformSettingsPage />);

    expect(await screen.findByText('API kapalı')).toBeInTheDocument();
    expect(screen.getAllByText('API kapalı')).toHaveLength(1);
    expect(screen.getAllByText('Kapalı')).toHaveLength(1);
  });
});

describe('ConnectedAccountsPage primary badge', () => {
  it('renders a single primary badge when several enabled channels are flagged primary', async () => {
    const connection = makeConnection();
    connection.channels = [
      { ...connection.channels[0], id: 'ch_1', channel_name: 'Kanal Bir', is_primary: true },
      { ...connection.channels[0], id: 'ch_2', channel_name: 'Kanal İki', is_primary: true },
    ];
    mockContext.connections = [connection];
    api.listConnections.mockResolvedValue({ items: [connection], total: 1 });

    render(<ConnectedAccountsPage />);

    expect(await screen.findByText('Kanal Bir')).toBeInTheDocument();
    expect(screen.getAllByText('birincil')).toHaveLength(1);
  });

  it('does not label a disabled legacy primary channel', async () => {
    const connection = makeConnection();
    connection.channels = [
      { ...connection.channels[0], id: 'ch_enabled', channel_name: 'Kanal Bir', is_primary: false, is_enabled: true },
      { ...connection.channels[0], id: 'ch_legacy', channel_name: 'UC_RESILIENCE', is_primary: true, is_enabled: false },
    ];
    mockContext.connections = [connection];
    api.listConnections.mockResolvedValue({ items: [connection], total: 1 });

    render(<ConnectedAccountsPage />);

    expect(await screen.findByText('UC_RESILIENCE')).toBeInTheDocument();
    expect(screen.queryByText('birincil')).not.toBeInTheDocument();
  });
});

describe('ConnectedAccountsPage disconnect confirmation', () => {
  it('asks for in-app confirmation before disconnecting an account', async () => {
    const user = userEvent.setup();
    const connection = makeConnection();
    mockContext.connections = [connection];
    api.listConnections.mockResolvedValue({ items: [connection], total: 1 });

    render(<ConnectedAccountsPage />);
    await user.click(await screen.findByRole('button', { name: /Bağlantıyı Kes/ }));

    expect(api.disconnectConnection).not.toHaveBeenCalled();
    expect(screen.getByText('Hesap Bağlantısını Kes')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Evet, Bağlantıyı Kes' }));

    await waitFor(() => expect(api.disconnectConnection).toHaveBeenCalledWith('conn_1'));
  });
});
