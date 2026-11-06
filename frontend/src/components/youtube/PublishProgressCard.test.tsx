import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PublishProgressCard } from './PublishProgressCard';
import { ToastProvider } from '../ui/toast';
import { apiService } from '../../services/api';
import type { PublishRecord } from '../../types/publish';

vi.mock('../../services/api', () => ({
  apiService: {
    getPublishRecord: vi.fn(),
    resumePublish: vi.fn(),
    cancelPublish: vi.fn(),
  },
}));

const api = apiService as unknown as Record<string, ReturnType<typeof vi.fn>>;

const record: PublishRecord = {
  id: 'pub-1',
  media_asset_id: 'asset-1',
  platform: 'youtube',
  title: 'Test Yüklemesi',
  description: '',
  tags: [],
  category_id: '22',
  privacy_status: 'private',
  status: 'uploading',
  progress_percentage: 40,
  uploaded_bytes: 4_000_000,
  total_bytes: 10_000_000,
  created_at: '2026-11-06T08:00:00Z',
  updated_at: '2026-11-06T08:01:00Z',
};

describe('PublishProgressCard cancel flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getPublishRecord.mockResolvedValue(record);
  });

  it('asks for confirmation before cancelling the upload', () => {
    render(<PublishProgressCard initialRecord={record} />);

    fireEvent.click(screen.getByRole('button', { name: 'İptal Et' }));

    expect(screen.getByText('Yüklemeyi İptal Et')).toBeInTheDocument();
    expect(api.cancelPublish).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Vazgeç' }));

    expect(screen.queryByText('Yüklemeyi İptal Et')).toBeNull();
    expect(api.cancelPublish).not.toHaveBeenCalled();
  });

  it('cancels the upload after confirmation', async () => {
    api.cancelPublish.mockResolvedValue({ ...record, status: 'cancelled' });
    render(<PublishProgressCard initialRecord={record} />);

    fireEvent.click(screen.getByRole('button', { name: 'İptal Et' }));
    fireEvent.click(screen.getByRole('button', { name: 'Evet, İptal Et' }));

    await waitFor(() => expect(api.cancelPublish).toHaveBeenCalledWith('pub-1'));
    await waitFor(() => expect(screen.queryByText('Yüklemeyi İptal Et')).toBeNull());
  });

  it('shows resume failures as a toast', async () => {
    api.resumePublish.mockRejectedValue(new Error('bağlantı hatası'));
    render(
      <ToastProvider>
        <PublishProgressCard initialRecord={{ ...record, status: 'paused' }} />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Devam Ettir' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Yükleme devam ettirilemedi');
    expect(alert).toHaveTextContent('bağlantı hatası');
  });
});
