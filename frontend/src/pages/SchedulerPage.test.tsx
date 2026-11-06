import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SchedulerPage } from './SchedulerPage';
import { apiService } from '../services/api';
import type { ScheduledPublish, SchedulerStatusResponse } from '../types/schedule';

const SCHEDULER_STATUS: SchedulerStatusResponse = {
  is_running: true,
  check_interval_seconds: 30,
  last_tick_at: '2026-11-06T08:59:30Z',
  active_count: 1,
  upcoming_count: 1,
  failed_count: 0,
  missed_count: 0,
  published_count: 0,
};

const BASE_SCHEDULE: ScheduledPublish = {
  id: 'sched-1',
  media_asset_id: 'asset-1',
  platform: 'youtube',
  title: 'Antik Roma Belgeseli #1',
  description: 'Plan açıklaması',
  tags: ['belgesel'],
  privacy_status: 'private',
  scheduled_at_utc: '2026-11-10T09:00:00Z',
  timezone: 'Europe/Istanbul',
  status: 'scheduled',
  attempt_count: 0,
  max_attempts: 3,
  created_at: '2026-11-06T08:00:00Z',
  updated_at: '2026-11-06T08:00:00Z',
  version: 1,
};

vi.mock('../context/ChannelContext', () => ({
  useChannelContext: () => ({
    activeChannel: { id: 'ch1', channel_name: 'Test Kanalı' },
    connections: [],
    channels: [],
    selection: null,
    isLoading: false,
    error: null,
    hasChannels: true,
    refresh: vi.fn(),
    selectChannel: vi.fn(),
  }),
}));

vi.mock('../services/api', () => ({
  apiService: {
    listSchedules: vi.fn(),
    getSchedulerStatus: vi.fn(),
    updateSchedule: vi.fn(),
    cancelSchedule: vi.fn(),
    retrySchedule: vi.fn(),
  },
}));

const api = apiService as unknown as Record<string, ReturnType<typeof vi.fn>>;

async function renderListWith(schedule: ScheduledPublish) {
  api.listSchedules.mockResolvedValue({ items: [schedule], total: 1 });
  api.getSchedulerStatus.mockResolvedValue(SCHEDULER_STATUS);
  render(<SchedulerPage videos={[]} />);

  fireEvent.click(await screen.findByRole('button', { name: /Liste/ }));
  await screen.findByText('Planlanan Zaman');
  await screen.findByText(schedule.title);
}

describe('SchedulerPage edit, cancel and retry', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('cancels a scheduled publish through the backend contract', async () => {
    await renderListWith(BASE_SCHEDULE);
    const cancelled = { ...BASE_SCHEDULE, status: 'cancelled' as const, version: 2 };
    api.cancelSchedule.mockResolvedValue(cancelled);
    api.listSchedules.mockResolvedValue({ items: [cancelled], total: 1 });

    fireEvent.click(screen.getByTitle('Planı İptal Et'));
    fireEvent.click(await screen.findByRole('button', { name: 'Evet, İptal Et' }));

    await waitFor(() => expect(api.cancelSchedule).toHaveBeenCalledWith('sched-1'));
    await screen.findByText('İptal Edildi');
    expect(screen.queryByTitle('Planı Düzenle')).toBeNull();
  });

  it('opens the edit modal prefilled and saves via updateSchedule', async () => {
    await renderListWith(BASE_SCHEDULE);
    api.updateSchedule.mockResolvedValue({
      ...BASE_SCHEDULE,
      title: 'Güncellenmiş Başlık',
      version: 2,
    });

    fireEvent.click(screen.getByTitle('Planı Düzenle'));

    const titleInput = await screen.findByDisplayValue(BASE_SCHEDULE.title);
    expect(screen.getByText('Yayın Planını Düzenle')).toBeInTheDocument();
    const dateInput = document.querySelector('input[type="datetime-local"]') as HTMLInputElement;
    expect(dateInput.value).toMatch(/^2026-11-10T/);

    fireEvent.change(titleInput, { target: { value: 'Güncellenmiş Başlık' } });
    fireEvent.click(screen.getByRole('button', { name: 'Değişiklikleri Kaydet' }));

    await waitFor(() =>
      expect(api.updateSchedule).toHaveBeenCalledWith(
        'sched-1',
        expect.objectContaining({
          title: 'Güncellenmiş Başlık',
          timezone: 'Europe/Istanbul',
          privacy_status: 'private',
          scheduled_at: expect.stringMatching(/^2026-11-10T/),
        }),
      ),
    );
  });

  it('retries a failed publish and reflects the new status', async () => {
    const failed = { ...BASE_SCHEDULE, status: 'failed' as const, attempt_count: 3 };
    await renderListWith(failed);
    const retried = { ...failed, status: 'scheduled' as const, attempt_count: 0 };
    api.retrySchedule.mockResolvedValue(retried);
    api.listSchedules.mockResolvedValue({ items: [retried], total: 1 });

    fireEvent.click(screen.getByTitle('Tekrar Dene'));

    await waitFor(() => expect(api.retrySchedule).toHaveBeenCalledWith('sched-1'));
    await waitFor(() => expect(screen.getAllByText('Planlandı').length).toBeGreaterThanOrEqual(2));
  });
});
