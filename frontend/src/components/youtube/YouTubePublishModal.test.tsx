import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { YouTubePublishModal } from './YouTubePublishModal';
import { apiService } from '../../services/api';
import type { MediaAsset } from '../../types/media';
import type { PublishRecord } from '../../types/publish';
import type { ScheduledPublish } from '../../types/schedule';

vi.mock('../../services/api', () => ({
  apiService: {
    listChannelPlaylists: vi.fn(),
    uploadCustomThumbnail: vi.fn(),
    startPublish: vi.fn(),
    createSchedule: vi.fn(),
    getThumbnailUrl: vi.fn(() => 'http://localhost/api/v1/media/m1/thumbnail'),
  },
}));

const api = apiService as unknown as {
  listChannelPlaylists: ReturnType<typeof vi.fn>;
  uploadCustomThumbnail: ReturnType<typeof vi.fn>;
  startPublish: ReturnType<typeof vi.fn>;
  createSchedule: ReturnType<typeof vi.fn>;
  getThumbnailUrl: ReturnType<typeof vi.fn>;
};

const asset: MediaAsset = {
  id: 'm1',
  filename: 'demo.mp4',
  original_filename: 'demo.mp4',
  file_path: '/tmp/demo.mp4',
  file_size_bytes: 5_000_000,
  mime_type: 'video/mp4',
  sha256_hash: 'hash',
  status: 'ready',
  thumbnail_path: null,
  created_at: '2026-11-01T10:00:00',
  updated_at: '2026-11-01T10:00:00',
  metadata: null,
};

const playlistResponse = {
  source: 'api',
  items: [
    { playlist_id: 'PL_ONE', title: 'Liste Bir', description: '', item_count: 3 },
    { playlist_id: 'PL_TWO', title: 'Liste İki', description: '', item_count: null },
  ],
};

function renderModal(overrides: Partial<React.ComponentProps<typeof YouTubePublishModal>> = {}) {
  const onPublishStarted = vi.fn();
  const onClose = vi.fn();
  const utils = render(
    <YouTubePublishModal
      asset={asset}
      isOpen
      onClose={onClose}
      onPublishStarted={onPublishStarted}
      channelId="ch1"
      channelName="Kanal Bir"
      {...overrides}
    />
  );
  return { ...utils, onPublishStarted, onClose };
}

function playlistSelect(): HTMLSelectElement {
  const selects = Array.from(document.querySelectorAll('select'));
  const select = selects.find((el) =>
    Array.from(el.options).some((option) => option.textContent?.startsWith('Liste Bir'))
  );
  if (!select) throw new Error('playlist select not found');
  return select as HTMLSelectElement;
}

describe('YouTubePublishModal upload studio', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listChannelPlaylists.mockResolvedValue(playlistResponse);
    (URL as typeof URL & { createObjectURL: () => string }).createObjectURL = vi.fn(
      () => 'blob:preview'
    );
    (URL as typeof URL & { revokeObjectURL: () => void }).revokeObjectURL = vi.fn();
  });

  it('loads channel playlists and sends the selected playlist with publish', async () => {
    api.startPublish.mockResolvedValue({ id: 'p1', status: 'pending' } as unknown as PublishRecord);
    const { onPublishStarted } = renderModal();

    await waitFor(() => expect(api.listChannelPlaylists).toHaveBeenCalledWith(50, 'ch1'));
    await waitFor(() => expect(playlistSelect()).toBeEnabled());

    await userEvent.selectOptions(playlistSelect(), 'PL_ONE');
    await userEvent.click(screen.getByRole('button', { name: /Yüklemeyi Başlat/ }));

    await waitFor(() => expect(api.startPublish).toHaveBeenCalledTimes(1));
    expect(api.startPublish).toHaveBeenCalledWith(
      expect.objectContaining({
        media_asset_id: 'm1',
        channel_id: 'ch1',
        playlist_id: 'PL_ONE',
        category_id: '22',
        privacy_status: 'private',
        thumbnail_path: null,
      })
    );
    expect(onPublishStarted).toHaveBeenCalledWith(expect.objectContaining({ id: 'p1' }));
  });

  it('uploads a custom thumbnail and uses the returned path on publish', async () => {
    api.uploadCustomThumbnail.mockResolvedValue({
      media_id: 'm1',
      thumbnail_path: '/media/custom_thumb_m1_abcd1234.png',
      file_size_bytes: 68,
    });
    api.startPublish.mockResolvedValue({ id: 'p2', status: 'pending' } as unknown as PublishRecord);
    renderModal();

    const file = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], 'cover.png', {
      type: 'image/png',
    });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(api.uploadCustomThumbnail).toHaveBeenCalledWith('m1', file));
    await waitFor(() => expect(screen.getByText('Değiştir')).toBeInTheDocument());

    await userEvent.click(screen.getByRole('button', { name: /Yüklemeyi Başlat/ }));

    await waitFor(() => expect(api.startPublish).toHaveBeenCalledTimes(1));
    expect(api.startPublish).toHaveBeenCalledWith(
      expect.objectContaining({ thumbnail_path: '/media/custom_thumb_m1_abcd1234.png' })
    );
  });

  it('rejects unsupported thumbnail types without calling the API', async () => {
    renderModal();

    const file = new File([new Uint8Array([0x47, 0x49, 0x46])], 'cover.gif', {
      type: 'image/gif',
    });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    expect(
      await screen.findByText('Kapak görseli JPEG veya PNG olmalıdır.')
    ).toBeInTheDocument();
    expect(api.uploadCustomThumbnail).not.toHaveBeenCalled();
  });

  it('creates an inline schedule with playlist and thumbnail fields', async () => {
    const scheduled = {
      id: 's1',
      scheduled_at_utc: '2026-11-08T12:00:00+00:00',
      timezone: 'Europe/Istanbul',
    } as unknown as ScheduledPublish;
    api.createSchedule.mockResolvedValue(scheduled);
    renderModal();

    await waitFor(() => expect(playlistSelect()).toBeEnabled());
    await userEvent.selectOptions(playlistSelect(), 'PL_TWO');
    await userEvent.click(screen.getByRole('button', { name: /İleri bir tarihe planla/ }));
    await userEvent.click(screen.getByRole('button', { name: /Yayını Planla/ }));

    await waitFor(() => expect(api.createSchedule).toHaveBeenCalledTimes(1));
    expect(api.createSchedule).toHaveBeenCalledWith(
      expect.objectContaining({
        media_asset_id: 'm1',
        channel_id: 'ch1',
        playlist_id: 'PL_TWO',
        category_id: '22',
        privacy_status: 'private',
        timezone: expect.any(String),
        scheduled_at: expect.any(String),
      })
    );
    expect(await screen.findByText('Yayın planlandı')).toBeInTheDocument();
  });

  it('blocks playlist selection when the connection cannot write to playlists', async () => {
    renderModal({ playlistWriteAllowed: false });

    await waitFor(() => expect(api.listChannelPlaylists).toHaveBeenCalled());
    expect(playlistSelect()).toBeDisabled();
    expect(
      screen.getByText(/YouTube yazma izni \(comments capability\) gerekir/)
    ).toBeInTheDocument();
  });
});
