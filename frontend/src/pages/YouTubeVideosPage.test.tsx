import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { YouTubeVideosPage } from './YouTubeVideosPage';
import { apiService } from '../services/api';
import type { CapabilityName } from '../lib/capabilities';
import type { CapabilityStatus, PlatformConnection } from '../types/account';
import type { ChannelVideo } from '../types/creator';

const CAPABILITIES: CapabilityName[] = [
  'identity',
  'channel_read',
  'analytics',
  'upload',
  'comments',
  'revenue',
];

function connectionWith(
  upload: 'active' | 'scope_required',
  comments: 'active' | 'scope_required' = 'scope_required'
): PlatformConnection {
  const capabilities: CapabilityStatus[] = CAPABILITIES.map((name) => {
    const status =
      name === 'upload'
        ? upload
        : name === 'comments'
          ? comments
          : name === 'identity' || name === 'channel_read'
            ? 'active'
            : 'scope_required';
    return {
      capability: name,
      status,
      granted: status === 'active',
      optional: name === 'revenue',
      required_scopes: [],
    };
  });
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
    listChannelVideos: vi.fn(),
    listVideoCategories: vi.fn(),
    updateChannelVideo: vi.fn(),
    setVideoThumbnail: vi.fn(),
    deleteChannelVideo: vi.fn(),
  },
}));

const api = apiService as unknown as {
  listChannelVideos: ReturnType<typeof vi.fn>;
  listVideoCategories: ReturnType<typeof vi.fn>;
  setVideoThumbnail: ReturnType<typeof vi.fn>;
  deleteChannelVideo: ReturnType<typeof vi.fn>;
};

const VIDEO: ChannelVideo = {
  video_id: 'v1',
  title: 'Bölüm 1',
  description: '',
  tags: [],
  privacy_status: 'public',
};

beforeEach(() => {
  vi.clearAllMocks();
  mockContext.connections = [connectionWith('active')];
  api.listChannelVideos.mockResolvedValue({
    items: [VIDEO],
    next_page_token: null,
    source: 'youtube_data_api',
  });
  api.listVideoCategories.mockResolvedValue({ items: [] });
});

describe('YouTubeVideosPage thumbnail action', () => {
  it('refuses thumbnail upload without the upload capability', async () => {
    mockContext.connections = [connectionWith('scope_required')];
    render(<YouTubeVideosPage />);

    await userEvent.click(await screen.findByRole('button', { name: /Kapak/ }));

    expect(
      await screen.findByText(/kapağı değiştirmek için YouTube yükleme izni gerekiyor/i)
    ).toBeInTheDocument();
    expect(api.setVideoThumbnail).not.toHaveBeenCalled();
  });

  it('uploads a PNG cover and refreshes the list', async () => {
    api.setVideoThumbnail.mockResolvedValue({ video_id: 'v1', updated: true, source: 'youtube_data_api' });
    render(<YouTubeVideosPage />);

    await userEvent.click(await screen.findByRole('button', { name: /Kapak/ }));

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], 'cover.png', {
      type: 'image/png',
    });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(api.setVideoThumbnail).toHaveBeenCalledWith('v1', file, 'ch1'));
    expect(await screen.findByText(/kapağı güncellendi/i)).toBeInTheDocument();
    await waitFor(() => expect(api.listChannelVideos).toHaveBeenCalledTimes(2));
  });

  it('rejects unsupported image types before calling the API', async () => {
    render(<YouTubeVideosPage />);

    await userEvent.click(await screen.findByRole('button', { name: /Kapak/ }));

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['gif'], 'cover.gif', { type: 'image/gif' });
    fireEvent.change(input, { target: { files: [file] } });

    expect(await screen.findByText(/JPEG veya PNG olmalıdır/i)).toBeInTheDocument();
    expect(api.setVideoThumbnail).not.toHaveBeenCalled();
  });
});

describe('YouTubeVideosPage delete action', () => {
  it('deletes a video only after confirmation', async () => {
    mockContext.connections = [connectionWith('active', 'active')];
    api.deleteChannelVideo.mockResolvedValue({ success: true, video_id: 'v1' });

    render(<YouTubeVideosPage />);

    await userEvent.click(await screen.findByRole('button', { name: /^Sil$/ }));
    expect(await screen.findByText(/kalıcı olarak silinecek/i)).toBeInTheDocument();
    expect(api.deleteChannelVideo).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: 'Videoyu sil' }));

    await waitFor(() => expect(api.deleteChannelVideo).toHaveBeenCalledWith('v1', 'ch1'));
    expect(await screen.findByText(/videosu YouTube'dan silindi/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryAllByText('Bölüm 1')).toHaveLength(0));
    expect(await screen.findByText('Kanalda video yok')).toBeInTheDocument();
  });

  it('cancels deletion without calling the API', async () => {
    mockContext.connections = [connectionWith('active', 'active')];
    render(<YouTubeVideosPage />);

    await userEvent.click(await screen.findByRole('button', { name: /^Sil$/ }));
    await userEvent.click(await screen.findByRole('button', { name: 'İptal' }));

    expect(api.deleteChannelVideo).not.toHaveBeenCalled();
  });

  it('explains the missing capability instead of opening the dialog', async () => {
    render(<YouTubeVideosPage />);

    await userEvent.click(await screen.findByRole('button', { name: /^Sil$/ }));

    expect(
      await screen.findByText(/silmek için yorum yönetimi izni gerekiyor/i)
    ).toBeInTheDocument();
    expect(api.deleteChannelVideo).not.toHaveBeenCalled();
  });
});
