import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ChannelOverviewPage } from './ChannelOverviewPage';
import { apiService } from '../services/api';
import type { AnalyticsResponse } from '../types/creator';

const mockContext = {
  connections: [],
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
    getChannelOverview: vi.fn(),
    getChannelAnalytics: vi.fn(),
    listChannelVideos: vi.fn(),
  },
}));

const api = apiService as unknown as {
  getChannelOverview: ReturnType<typeof vi.fn>;
  getChannelAnalytics: ReturnType<typeof vi.fn>;
  listChannelVideos: ReturnType<typeof vi.fn>;
};

const OVERVIEW = {
  channel: {
    channel_id: 'UC_FAKE',
    title: 'Test Kanalı',
    description: 'Kanal açıklaması',
    subscriber_count: 1500,
    video_count: 4,
    view_count: 25000,
    hidden_subscriber_count: false,
  },
  playlists: [{ playlist_id: 'pl1', title: 'Seri', item_count: 3 }],
  source: 'youtube_data_api',
};

function analyticsResponse(): AnalyticsResponse {
  return {
    range: { key: '28', start_date: '2026-10-10', end_date: '2026-11-06', days: 28 },
    analytics: {
      available: true,
      source: 'youtube_analytics_api',
      start_date: '2026-10-10',
      end_date: '2026-11-06',
      metrics: ['views', 'estimatedMinutesWatched', 'averageViewDuration'],
      dimensions: ['video'],
      totals: {
        views: 150,
        estimatedMinutesWatched: 120,
        averageViewPercentage: 42.5,
        subscribersGained: 4,
        subscribersLost: 1,
      },
      rows: [
        {
          dimensions: { video: 'v1' },
          metrics: { views: 90, estimatedMinutesWatched: 60, averageViewDuration: 30 },
        },
      ],
      fetched_at: '2026-11-06T10:00:00Z',
    },
    comparison: {
      available: true,
      range: { start_date: '2026-09-12', end_date: '2026-10-09', days: 28 },
      totals: { views: 50, estimatedMinutesWatched: 0 },
      deltas: {
        views: { current: 150, previous: 50, change: 100, percent: 200 },
        estimatedMinutesWatched: { current: 120, previous: 0, change: 120, percent: null },
        averageViewPercentage: { current: 42.5, previous: 40, change: 2.5, percent: 6.25 },
      },
    },
    source: 'youtube_analytics_api',
    explanation: null,
    metric_notes: {},
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getChannelOverview.mockResolvedValue(OVERVIEW);
  api.getChannelAnalytics.mockResolvedValue(analyticsResponse());
  api.listChannelVideos.mockResolvedValue({
    items: [
      {
        video_id: 'v1',
        title: 'Bölüm 1',
        description: '',
        thumbnail_url: 'https://img.example/v1.jpg',
        privacy_status: 'public',
      },
    ],
    next_page_token: null,
    source: 'youtube_data_api',
  });
});

describe('ChannelOverviewPage insights', () => {
  it('requests the 28-day video report with comparison enabled', async () => {
    render(<ChannelOverviewPage onNavigate={vi.fn()} />);

    await waitFor(() =>
      expect(api.getChannelAnalytics).toHaveBeenCalledWith({
        range: '28',
        dimensions: ['video'],
        compare: true,
        channelId: 'ch1',
      })
    );
  });

  it('renders insight totals, deltas and top videos', async () => {
    render(<ChannelOverviewPage onNavigate={vi.fn()} />);

    expect(await screen.findByText('Son 28 gün')).toBeInTheDocument();
    expect(screen.getByText('150')).toBeInTheDocument();
    expect(screen.getByText('+200.0% · önceki dönem 50')).toBeInTheDocument();
    expect(screen.getByText('önceki dönemde veri yok')).toBeInTheDocument();
    expect(screen.getByText('+3')).toBeInTheDocument();
    expect(screen.getByText('Kazanılan 4 · Kaybedilen 1')).toBeInTheDocument();
    expect(screen.getByText('42,5%')).toBeInTheDocument();
    expect(screen.getByText('+6.3% · önceki dönem 40')).toBeInTheDocument();

    expect(screen.getByText('Öne çıkan videolar')).toBeInTheDocument();
    const link = screen.getByRole('link', { name: 'Bölüm 1' });
    expect(link).toHaveAttribute('href', 'https://www.youtube.com/watch?v=v1');
  });

  it('keeps channel data visible when analytics is unavailable', async () => {
    const unavailable = analyticsResponse();
    unavailable.analytics.available = false;
    unavailable.analytics.totals = {};
    unavailable.analytics.rows = [];
    unavailable.comparison = null;
    unavailable.explanation = 'Analitik izni gerekiyor.';
    api.getChannelAnalytics.mockResolvedValue(unavailable);

    render(<ChannelOverviewPage onNavigate={vi.fn()} />);

    expect(await screen.findByText('Test Kanalı')).toBeInTheDocument();
    expect(screen.getByText('Seri')).toBeInTheDocument();
    expect(screen.getByText('Analitik izni gerekiyor.')).toBeInTheDocument();
    expect(screen.queryByText('Öne çıkan videolar')).not.toBeInTheDocument();
  });

  it('keeps channel data visible when the analytics request fails', async () => {
    api.getChannelAnalytics.mockRejectedValue(new Error('Analitik kotası doldu.'));

    render(<ChannelOverviewPage onNavigate={vi.fn()} />);

    expect(await screen.findByText('Test Kanalı')).toBeInTheDocument();
    expect(screen.getByText('Analitik kotası doldu.')).toBeInTheDocument();
    expect(screen.getByText('Seri')).toBeInTheDocument();
  });
});
