import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { VideoLibraryPage } from './VideoLibraryPage';

const apiMock = vi.hoisted(() => ({
  getRenderVideoUrl: vi.fn((jobId: string) => `/api/v1/studio/renders/${jobId}/video`),
  getRenderSubtitlesUrl: vi.fn(
    (jobId: string) => `/api/v1/studio/renders/${jobId}/subtitles`
  ),
}));

vi.mock('../services/api', () => ({ apiService: apiMock }));

const project = {
  id: 'proj_demo',
  title: 'Ali ve Ayşe Kafe Buluşması',
  description: 'Kafe hikâyesi',
  status: 'completed',
  scene_graph: null,
  total_duration_seconds: 9,
  scene_count: 2,
  character_count: 2,
  created_at: '2026-11-04T10:00:00',
  updated_at: '2026-11-04T10:10:00',
};

const job = {
  id: 'comp_render_completed',
  project_id: 'proj_demo',
  status: 'completed' as const,
  progress_percent: 100,
  current_step: 'Completed',
  output_video_path: '/tmp/video.mp4',
  output_metadata: {
    video_file_path: '/tmp/video.mp4',
    file_size_bytes: 2048,
    duration_seconds: 9,
    width: 1080,
    height: 1920,
    fps: 30,
    video_codec: 'h264',
    pixel_format: 'yuv420p',
    container: 'mp4',
    frame_count: 270,
    render_duration_seconds: 12,
    engine: 'FFMPEG_COMPOSITION',
    composition_name: 'Dikey Kompozisyon',
    format: '9:16',
    subtitle_file_path: '/tmp/subtitles.srt',
    subtitle_cue_count: 2,
  },
  error_message: null,
  created_at: '2026-11-04T10:20:00',
  started_at: '2026-11-04T10:20:01',
  completed_at: '2026-11-04T10:21:00',
};

describe('VideoLibraryPage studio outputs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('lists real studio renders with project relation and export actions', async () => {
    const user = userEvent.setup();
    const onOpenProject = vi.fn();
    render(
      <VideoLibraryPage
        videos={[]}
        isLoading={false}
        studioRenders={[job]}
        studioProjects={[project]}
        onOpenProject={onOpenProject}
        onSelectVideo={vi.fn()}
        onRequestDelete={vi.fn()}
        onNavigateImport={vi.fn()}
      />
    );

    expect(screen.getByText('Yüklenen medya')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Studio çıktıları/i }));

    expect(screen.getAllByText('Ali ve Ayşe Kafe Buluşması').length).toBeGreaterThan(0);
    expect(screen.getAllByText('1080 × 1920').length).toBeGreaterThan(0);
    expect(screen.getAllByText('9:16').length).toBeGreaterThan(0);

    const download = screen.getByRole('link', { name: /MP4 indir/i });
    expect(download).toHaveAttribute('href', '/api/v1/studio/renders/comp_render_completed/video');
    expect(screen.getByRole('link', { name: /SRT indir/i })).toHaveAttribute(
      'href',
      '/api/v1/studio/renders/comp_render_completed/subtitles'
    );

    await user.click(screen.getByRole('button', { name: /Projeye dön/i }));
    expect(onOpenProject).toHaveBeenCalledWith('proj_demo');
  });

  it('keeps the uploaded media empty state and supports switching back', async () => {
    const user = userEvent.setup();
    render(
      <VideoLibraryPage
        videos={[]}
        isLoading={false}
        studioRenders={[job]}
        studioProjects={[project]}
        onSelectVideo={vi.fn()}
        onRequestDelete={vi.fn()}
        onNavigateImport={vi.fn()}
      />
    );

    expect(await screen.findByText('Henüz Video Bulunmuyor')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Studio çıktıları/i }));
    await user.click(screen.getByRole('button', { name: /Yüklenen medya/i }));
    expect(screen.getByText('Henüz Video Bulunmuyor')).toBeInTheDocument();
  });
});
