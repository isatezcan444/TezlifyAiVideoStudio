import type { ComponentProps } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { VideoLibraryPage } from './VideoLibraryPage';
import type { MediaAsset } from '../types/media';

vi.mock('../services/api', () => ({ apiService: {} }));

const asset: MediaAsset = {
  id: 'media_demo',
  filename: 'kafe.mp4',
  original_filename: 'kafe-bulusmasi.mp4',
  file_path: '/tmp/kafe.mp4',
  file_size_bytes: 2048,
  mime_type: 'video/mp4',
  sha256_hash: 'demo',
  status: 'ready',
  thumbnail_path: null,
  created_at: '2026-11-04T10:00:00',
  updated_at: '2026-11-04T10:00:00',
  metadata: {
    duration_seconds: 9,
    width: 1080,
    height: 1920,
    fps: 30,
    video_codec: 'h264',
    audio_codec: 'aac',
    aspect_ratio: '9:16',
    probe_source: 'ffprobe',
    resolution_label: '1080x1920',
  },
};

function renderLibrary(overrides: Partial<ComponentProps<typeof VideoLibraryPage>> = {}) {
  const props = {
    videos: [asset],
    isLoading: false,
    onSelectVideo: vi.fn(),
    onRequestDelete: vi.fn(),
    onNavigateImport: vi.fn(),
    onPublishVideo: vi.fn(),
    onScheduleVideo: vi.fn(),
    ...overrides,
  };
  render(<VideoLibraryPage {...props} />);
  return props;
}

describe('VideoLibraryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the local media library grid with probe metadata', () => {
    renderLibrary();

    expect(screen.getByText('kafe-bulusmasi.mp4')).toBeInTheDocument();
    expect(screen.getByText('1080x1920')).toBeInTheDocument();
    expect(screen.getByText('00:09')).toBeInTheDocument();
  });

  it('opens the details action and publish/schedule callbacks', async () => {
    const user = userEvent.setup();
    const props = renderLibrary();

    await user.click(screen.getByTitle('Detay & Oynat'));
    expect(props.onSelectVideo).toHaveBeenCalledWith(asset);

    await user.click(screen.getByTitle("YouTube'a Yükle"));
    expect(props.onPublishVideo).toHaveBeenCalledWith(asset);

    await user.click(screen.getByTitle('Yayın Takvimine Ekle'));
    expect(props.onScheduleVideo).toHaveBeenCalledWith(asset);
  });

  it('filters by search query and supports the list view', async () => {
    const user = userEvent.setup();
    renderLibrary();

    await user.click(screen.getByTitle('Liste Görünümü'));
    expect(screen.getByRole('table')).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText('Video adı veya çözünürlükle ara...'), 'yok-boyle-video');
    expect(
      screen.getByText(/"yok-boyle-video"\s*aramasıyla eşleşen video bulunamadı\./)
    ).toBeInTheDocument();
  });

  it('shows the empty state with the import action', async () => {
    const user = userEvent.setup();
    const props = renderLibrary({ videos: [] });

    expect(screen.getByText('Henüz Video Bulunmuyor')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /İlk Videoyu İçe Aktar/i }));
    expect(props.onNavigateImport).toHaveBeenCalled();
  });
});
