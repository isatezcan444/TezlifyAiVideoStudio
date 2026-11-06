import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AnalyticsPage } from './AnalyticsPage';
import { apiService } from '../services/api';
import type { CapabilityName } from '../lib/capabilities';
import type { CapabilityStatus, PlatformConnection } from '../types/account';
import type { AnalyticsResponse } from '../types/creator';

const CAPABILITIES: CapabilityName[] = [
  'identity',
  'channel_read',
  'analytics',
  'upload',
  'comments',
  'revenue',
];

function connectionWith(): PlatformConnection {
  const capabilities: CapabilityStatus[] = CAPABILITIES.map((name) => ({
    capability: name,
    status: name === 'revenue' ? 'scope_required' : 'active',
    granted: name !== 'revenue',
    optional: name === 'revenue',
    required_scopes: [],
  }));
  return {
    id: 'conn_1',
    platform: 'youtube',
    account_name: 'Test Hesabı',
    capabilities,
  } as unknown as PlatformConnection;
}

const mockContext = {
  connections: [] as PlatformConnection[],
  channels: [],
  activeChannel: { id: 'ch1', platform_connection_id: 'conn_1' } as any,
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
    getChannelAnalytics: vi.fn(),
    listChannelVideos: vi.fn(),
  },
}));

const api = apiService as unknown as {
  getChannelAnalytics: ReturnType<typeof vi.fn>;
  listChannelVideos: ReturnType<typeof vi.fn>;
};

const METRIC_KEYS = [
  'views',
  'estimatedMinutesWatched',
  'averageViewDuration',
  'averageViewPercentage',
  'subscribersGained',
  'subscribersLost',
];

function baseResponse(): AnalyticsResponse {
  return {
    range: { key: '28', start_date: '2026-10-01', end_date: '2026-10-28', days: 28 },
    analytics: {
      available: true,
      source: 'youtube_analytics_api',
      start_date: '2026-10-01',
      end_date: '2026-10-28',
      metrics: METRIC_KEYS,
      dimensions: ['day'],
      totals: { views: 150, estimatedMinutesWatched: 100 },
      rows: [
        {
          dimensions: { day: '2026-10-01' },
          metrics: { views: 100, estimatedMinutesWatched: 60 },
        },
      ],
      fetched_at: '2026-10-28T10:00:00Z',
    },
    comparison: {
      available: true,
      range: { start_date: '2026-09-01', end_date: '2026-09-28', days: 28 },
      totals: { views: 50, estimatedMinutesWatched: 0 },
      deltas: {
        views: { current: 150, previous: 50, change: 100, percent: 200 },
        estimatedMinutesWatched: { current: 100, previous: 0, change: 100, percent: null },
      },
    },
    source: 'youtube_analytics_api',
    explanation: null,
    metric_notes: {},
  };
}

function videoResponse(compare = false): AnalyticsResponse {
  const response = baseResponse();
  response.analytics.dimensions = ['video'];
  response.analytics.rows = [
    {
      dimensions: { video: 'v1' },
      metrics: { views: 80, estimatedMinutesWatched: 40, averageViewDuration: 30 },
    },
  ];
  response.comparison = compare
    ? {
        available: true,
        range: { start_date: '2026-09-01', end_date: '2026-09-28', days: 28 },
        totals: { views: 50 },
        deltas: { views: { current: 80, previous: 50, change: 30, percent: 60 } },
        rows: [
          {
            key: 'v1',
            dimensions: { video: 'v1' },
            previous_metrics: { views: 50, estimatedMinutesWatched: 25 },
            deltas: {
              views: { current: 80, previous: 50, change: 30, percent: 60 },
            },
          },
        ],
      }
    : null;
  return response;
}

let createdBlobs: Blob[] = [];

beforeEach(() => {
  vi.clearAllMocks();
  createdBlobs = [];
  mockContext.connections = [connectionWith()];
  api.getChannelAnalytics.mockImplementation(async (params: any) =>
    params?.dimensions?.[0] === 'video'
      ? videoResponse(Boolean(params?.compare))
      : baseResponse()
  );
  api.listChannelVideos.mockResolvedValue({
    items: [
      {
        video_id: 'v1',
        title: 'Bölüm 1',
        description: '',
        tags: [],
        privacy_status: 'public',
      },
    ],
    next_page_token: null,
    source: 'youtube_data_api',
  });
  Object.defineProperty(URL, 'createObjectURL', {
    configurable: true,
    writable: true,
    value: vi.fn((blob: Blob) => {
      createdBlobs.push(blob);
      return 'blob:mock';
    }),
  });
  Object.defineProperty(URL, 'revokeObjectURL', {
    configurable: true,
    writable: true,
    value: vi.fn(),
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.readAsText(blob);
  });
}

function readBlobBytes(blob: Blob): Promise<Uint8Array> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
    reader.readAsArrayBuffer(blob);
  });
}

describe('AnalyticsPage comparison', () => {
  it('requests the previous period only when the comparison is enabled', async () => {
    render(<AnalyticsPage onNavigate={vi.fn()} />);

    await waitFor(() => expect(api.getChannelAnalytics).toHaveBeenCalledTimes(1));
    expect(api.getChannelAnalytics.mock.calls[0][0]).toMatchObject({
      range: '28',
      dimensions: ['day'],
      compare: false,
      channelId: 'ch1',
    });

    await userEvent.click(screen.getByLabelText('Önceki dönemle karşılaştır'));

    await waitFor(() =>
      expect(api.getChannelAnalytics).toHaveBeenLastCalledWith(
        expect.objectContaining({ compare: true })
      )
    );
  });

  it('renders the comparison window and percentage deltas', async () => {
    render(<AnalyticsPage onNavigate={vi.fn()} />);

    await userEvent.click(await screen.findByLabelText('Önceki dönemle karşılaştır'));

    expect(
      await screen.findByText(/Karşılaştırma dönemi: 2026-09-01 → 2026-09-28 \(28 gün\)/)
    ).toBeInTheDocument();
    expect(screen.getByText('+200.0% · önceki dönem 50')).toBeInTheDocument();
    expect(screen.getByText('önceki dönemde veri yok')).toBeInTheDocument();
  });
});

describe('AnalyticsPage video depth and CSV', () => {
  it('maps video ids to titles with a YouTube link', async () => {
    render(<AnalyticsPage onNavigate={vi.fn()} />);
    await screen.findByText('Gün kırılımı');

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'video' } });

    const link = await screen.findByRole('link', { name: 'Bölüm 1' });
    expect(link).toHaveAttribute('href', 'https://www.youtube.com/watch?v=v1');
    await waitFor(() =>
      expect(api.getChannelAnalytics).toHaveBeenLastCalledWith(
        expect.objectContaining({ dimensions: ['video'] })
      )
    );
  });

  it('exports the visible table as a semicolon CSV with a BOM', async () => {
    let downloadedName = '';
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(
      function (this: HTMLAnchorElement) {
        downloadedName = this.download;
      }
    );

    render(<AnalyticsPage onNavigate={vi.fn()} />);
    await screen.findByText('Gün kırılımı');

    await userEvent.click(screen.getByRole('button', { name: /CSV indir/ }));

    expect(createdBlobs).toHaveLength(1);
    const bytes = await readBlobBytes(createdBlobs[0]);
    expect(Array.from(bytes.slice(0, 3))).toEqual([0xef, 0xbb, 0xbf]);
    const content = await readBlob(createdBlobs[0]);
    expect(content).toContain('Gün;Görüntüleme;Tahmini izlenme (dk)');
    expect(content).toContain('2026-10-01;100;60');
    expect(content).toContain('Toplam');
    expect(downloadedName).toBe('tezlify-analitik-day-2026-10-01-2026-10-28.csv');
  });

  it('shows per-row previous-period deltas and exports them to CSV', async () => {
    let downloadedName = '';
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(
      function (this: HTMLAnchorElement) {
        downloadedName = this.download;
      }
    );

    render(<AnalyticsPage onNavigate={vi.fn()} />);
    await screen.findByText('Gün kırılımı');

    await userEvent.click(screen.getByLabelText('Önceki dönemle karşılaştır'));
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'video' } });

    await screen.findByRole('link', { name: 'Bölüm 1' });
    expect(await screen.findByText('+60.0%')).toBeInTheDocument();
    expect(
      screen.getByText(/Her satırda 2026-09-01 → 2026-09-28 dönemine göre değişim/)
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /CSV indir/ }));

    const content = await readBlob(createdBlobs[createdBlobs.length - 1]);
    expect(content).toContain('Video;Görüntüleme;Görüntüleme (önceki);Görüntüleme değişim %');
    expect(content).toContain('Bölüm 1;80;50;60');
    expect(downloadedName).toBe('tezlify-analitik-video-2026-10-01-2026-10-28.csv');
  });
});
