import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiService } from './api';
import type { ScheduledPublish } from '../types/schedule';

const SCHEDULE = {
  id: 'sched-1',
  media_asset_id: 'asset-1',
  platform: 'youtube',
  title: 'Planlanan Video',
  description: '',
  tags: [],
  privacy_status: 'private',
  scheduled_at_utc: '2026-11-10T09:00:00Z',
  timezone: 'Europe/Istanbul',
  status: 'cancelled',
  attempt_count: 0,
  max_attempts: 3,
  created_at: '2026-11-06T09:00:00Z',
  updated_at: '2026-11-06T09:00:00Z',
  version: 2,
} as ScheduledPublish;

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response;
}

describe('apiService scheduler contract', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('cancels with DELETE and unwraps the item envelope', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ success: true, message: 'Yayın planı iptal edildi.', item: SCHEDULE }),
    );

    const result = await apiService.cancelSchedule('sched-1');

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/scheduler/sched-1', { method: 'DELETE' });
    expect(result).toEqual(SCHEDULE);
    expect(result.status).toBe('cancelled');
  });

  it('accepts a bare schedule payload without the item envelope', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(SCHEDULE));

    await expect(apiService.cancelSchedule('sched-1')).resolves.toEqual(SCHEDULE);
  });

  it('updates via PATCH with a JSON body', async () => {
    const payload = {
      title: 'Yeni Başlık',
      scheduled_at: '2026-11-12T10:30:00.000Z',
      timezone: 'Europe/Istanbul',
      privacy_status: 'unlisted' as const,
    };
    fetchMock.mockResolvedValueOnce(jsonResponse({ ...SCHEDULE, ...payload, status: 'scheduled' }));

    const result = await apiService.updateSchedule('sched-1', payload);

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/scheduler/sched-1', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    expect(result.title).toBe('Yeni Başlık');
  });

  it('surfaces the backend error detail when cancel fails', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'Plan bulunamadı.' }, false, 404));

    await expect(apiService.cancelSchedule('missing')).rejects.toMatchObject({
      message: 'Plan bulunamadı.',
      statusCode: 404,
    });
  });
});
