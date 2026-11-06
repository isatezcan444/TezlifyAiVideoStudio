import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PlaylistsPage } from './PlaylistsPage';
import { apiService } from '../services/api';
import type { CapabilityName } from '../lib/capabilities';
import type { CapabilityStatus, PlatformConnection } from '../types/account';
import type { ChannelPlaylist, PlaylistItem } from '../types/creator';

const CAPABILITIES: CapabilityName[] = [
  'identity',
  'channel_read',
  'analytics',
  'upload',
  'comments',
  'revenue',
];

function connectionWith(comments: 'active' | 'scope_required'): PlatformConnection {
  const capabilities: CapabilityStatus[] = CAPABILITIES.map((name) => {
    const status =
      name === 'comments'
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
    listChannelPlaylists: vi.fn(),
    listPlaylistItems: vi.fn(),
    listChannelVideos: vi.fn(),
    createPlaylist: vi.fn(),
    addVideoToPlaylist: vi.fn(),
    removeVideoFromPlaylist: vi.fn(),
    updatePlaylist: vi.fn(),
    deletePlaylist: vi.fn(),
    movePlaylistItem: vi.fn(),
    grantCapabilities: vi.fn(),
  },
}));

vi.mock('../lib/youtubeOAuth', () => ({
  awaitYouTubeOAuth: vi.fn(),
  openOAuthPopup: vi.fn(),
}));

const api = apiService as unknown as {
  listChannelPlaylists: ReturnType<typeof vi.fn>;
  listPlaylistItems: ReturnType<typeof vi.fn>;
  listChannelVideos: ReturnType<typeof vi.fn>;
  createPlaylist: ReturnType<typeof vi.fn>;
  addVideoToPlaylist: ReturnType<typeof vi.fn>;
  removeVideoFromPlaylist: ReturnType<typeof vi.fn>;
  updatePlaylist: ReturnType<typeof vi.fn>;
  deletePlaylist: ReturnType<typeof vi.fn>;
  movePlaylistItem: ReturnType<typeof vi.fn>;
};

const PLAYLISTS: ChannelPlaylist[] = [
  { playlist_id: 'pl1', title: 'Liste Bir', description: 'İlk liste', item_count: 1 },
  { playlist_id: 'pl2', title: 'Liste İki', description: '', item_count: 0 },
];

const ITEMS: PlaylistItem[] = [
  {
    playlist_item_id: 'pli1',
    playlist_id: 'pl1',
    video_id: 'v1',
    title: 'Bölüm 1',
    position: 0,
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  mockContext.connections = [connectionWith('active')];
  api.listChannelPlaylists.mockResolvedValue({ items: PLAYLISTS, source: 'youtube_data_api' });
  api.listPlaylistItems.mockResolvedValue({ items: ITEMS, source: 'youtube_data_api' });
  api.listChannelVideos.mockResolvedValue({
    items: [
      { video_id: 'v1', title: 'Bölüm 1', description: '', tags: [] },
      { video_id: 'v2', title: 'Bölüm 2', description: '', tags: [] },
    ],
    source: 'youtube_data_api',
  });
});

describe('PlaylistsPage', () => {
  it('lists playlists and shows the selected playlist items', async () => {
    render(<PlaylistsPage />);

    expect(await screen.findByRole('button', { name: /Liste Bir/ })).toBeInTheDocument();
    expect(await screen.findByText(/sıra 1/)).toBeInTheDocument();
    expect(api.listPlaylistItems).toHaveBeenCalledWith('pl1', 50, 'ch1');

    await userEvent.click(screen.getByText('Liste İki'));
    await waitFor(() => expect(api.listPlaylistItems).toHaveBeenCalledWith('pl2', 50, 'ch1'));
  });

  it('blocks playlist creation without the comments capability', async () => {
    mockContext.connections = [connectionWith('scope_required')];
    render(<PlaylistsPage />);

    expect(await screen.findByText('Oynatma listesi yazma izni yok')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Yeni liste' }));

    expect(
      await screen.findByText(/oynatma listesi yazma izni gerekiyor/i)
    ).toBeInTheDocument();
    expect(api.createPlaylist).not.toHaveBeenCalled();
  });

  it('creates a playlist and selects the new one', async () => {
    api.createPlaylist.mockResolvedValue({
      playlist: { playlist_id: 'pl3', title: 'Yeni Seri', description: '', item_count: 0 },
      source: 'youtube_data_api',
    });
    render(<PlaylistsPage />);

    await userEvent.click(await screen.findByRole('button', { name: 'Yeni liste' }));
    await userEvent.type(screen.getByLabelText('Ad'), 'Yeni Seri');
    await userEvent.click(screen.getByRole('button', { name: 'Oluştur' }));

    await waitFor(() =>
      expect(api.createPlaylist).toHaveBeenCalledWith(
        { title: 'Yeni Seri', description: '', privacy_status: 'private' },
        'ch1'
      )
    );
    expect(await screen.findByText(/oynatma listesi oluşturuldu/i)).toBeInTheDocument();
  });

  it('adds an available video to the playlist', async () => {
    api.addVideoToPlaylist.mockResolvedValue({
      item: { playlist_item_id: 'pli2', playlist_id: 'pl1', video_id: 'v2', title: 'Bölüm 2' },
      source: 'youtube_data_api',
    });
    api.listPlaylistItems
      .mockResolvedValueOnce({ items: ITEMS, source: 'youtube_data_api' })
      .mockResolvedValue({
        items: [...ITEMS, { ...ITEMS[0], playlist_item_id: 'pli2', video_id: 'v2', title: 'Bölüm 2' }],
        source: 'youtube_data_api',
      });

    render(<PlaylistsPage />);

    const select = await screen.findByDisplayValue('Video seç');
    await userEvent.selectOptions(select, 'v2');
    await userEvent.click(screen.getByRole('button', { name: 'Ekle' }));

    await waitFor(() => expect(api.addVideoToPlaylist).toHaveBeenCalledWith('pl1', 'v2', 'ch1'));
    expect(await screen.findByText('Bölüm 2')).toBeInTheDocument();
  });

  it('removes a video from the playlist', async () => {
    api.removeVideoFromPlaylist.mockResolvedValue({
      success: true,
      playlist_id: 'pl1',
      video_id: 'v1',
    });

    render(<PlaylistsPage />);

    await userEvent.click(await screen.findByRole('button', { name: /Çıkar/ }));

    await waitFor(() => expect(api.removeVideoFromPlaylist).toHaveBeenCalledWith('pl1', 'v1', 'ch1'));
    // The row disappears; only the "add video" option still carries the title.
    await waitFor(() => expect(screen.queryAllByText('Bölüm 1')).toHaveLength(1));
    expect(await screen.findByText(/listesinden çıkarıldı/i)).toBeInTheDocument();
  });

  it('updates the selected playlist title', async () => {
    api.updatePlaylist.mockResolvedValue({
      playlist: { ...PLAYLISTS[0], title: 'Yeni Liste' },
      source: 'youtube_data_api',
    });

    render(<PlaylistsPage />);

    await userEvent.click(await screen.findByRole('button', { name: /Düzenle/ }));
    const titleInput = await screen.findByLabelText('Ad');
    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, 'Yeni Liste');
    await userEvent.click(screen.getByRole('button', { name: 'Kaydet' }));

    await waitFor(() =>
      expect(api.updatePlaylist).toHaveBeenCalledWith('pl1', { title: 'Yeni Liste' }, 'ch1')
    );
    expect(await screen.findByText(/oynatma listesi güncellendi/i)).toBeInTheDocument();
    expect(await screen.findAllByText('Yeni Liste')).not.toHaveLength(0);
  });

  it('does not send playlist updates when nothing changed', async () => {
    render(<PlaylistsPage />);

    await userEvent.click(await screen.findByRole('button', { name: /Düzenle/ }));
    await userEvent.click(await screen.findByRole('button', { name: 'Kaydet' }));

    expect(await screen.findByText(/değişiklik yapılmadı/i)).toBeInTheDocument();
    expect(api.updatePlaylist).not.toHaveBeenCalled();
  });

  it('deletes the selected playlist after confirmation', async () => {
    api.deletePlaylist.mockResolvedValue({ success: true, playlist_id: 'pl1' });

    render(<PlaylistsPage />);

    await userEvent.click(await screen.findByRole('button', { name: /^Sil$/ }));
    expect(await screen.findByText(/kalıcı olarak silinecek/i)).toBeInTheDocument();
    expect(api.deletePlaylist).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: 'Listeyi sil' }));

    await waitFor(() => expect(api.deletePlaylist).toHaveBeenCalledWith('pl1', 'ch1'));
    expect(await screen.findByText(/oynatma listesi silindi/i)).toBeInTheDocument();
  });

  it('moves a playlist item to the next position', async () => {
    const second: PlaylistItem = {
      playlist_item_id: 'pli2',
      playlist_id: 'pl1',
      video_id: 'v2',
      title: 'Bölüm 2',
      position: 1,
    };
    api.listPlaylistItems.mockResolvedValue({
      items: [...ITEMS, second],
      source: 'youtube_data_api',
    });
    api.movePlaylistItem.mockResolvedValue({
      success: true,
      playlist_id: 'pl1',
      video_id: 'v1',
      position: 1,
    });

    render(<PlaylistsPage />);

    const downButtons = await screen.findAllByRole('button', { name: 'Aşağı taşı' });
    await userEvent.click(downButtons[0]);

    await waitFor(() => expect(api.movePlaylistItem).toHaveBeenCalledWith('pl1', 'v1', 1, 'ch1'));
    expect(await screen.findByText(/liste sırası güncellendi/i)).toBeInTheDocument();
  });

  it('disables edit, delete and reorder without write capability', async () => {
    mockContext.connections = [connectionWith('scope_required')];
    render(<PlaylistsPage />);

    expect(await screen.findByRole('button', { name: /Düzenle/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /^Sil$/ })).toBeDisabled();
    for (const button of screen.getAllByRole('button', { name: 'Yukarı taşı' })) {
      expect(button).toBeDisabled();
    }
    for (const button of screen.getAllByRole('button', { name: 'Aşağı taşı' })) {
      expect(button).toBeDisabled();
    }
  });
});
