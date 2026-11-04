import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CompositionStudioPage } from './CompositionStudioPage';

const apiMock = vi.hoisted(() => ({
  listProjects: vi.fn(),
  getVoiceStatus: vi.fn(),
  getProjectComposition: vi.fn(),
  listProjectRenders: vi.fn(),
  saveProjectComposition: vi.fn(),
  startCompositionRender: vi.fn(),
  getRenderJob: vi.fn(),
  getRenderVideoUrl: vi.fn((jobId: string) => `/api/v1/studio/renders/${jobId}/video`),
  getRenderSubtitlesUrl: vi.fn((jobId: string) => `/api/v1/studio/renders/${jobId}/subtitles`),
}));

vi.mock('../services/api', () => ({ apiService: apiMock }));

const project = {
  id: 'proj_demo',
  title: 'Ali ve Ayşe Kafe Buluşması',
  description: 'Stage 4.5 frontend testi',
  status: 'draft',
  scene_graph: {
    scenes: [
      { scene_id: 'scene_01', dialogues: [] },
      { scene_id: 'scene_02', dialogues: [{ text: 'Merhaba Ayşe!' }] },
      { scene_id: 'scene_03', dialogues: [] },
    ],
  },
  total_duration_seconds: 8,
  scene_count: 3,
  character_count: 2,
  created_at: '2026-11-04T10:00:00',
  updated_at: '2026-11-04T10:00:00',
};

const baseComposition = {
  id: 'comp_proj_demo',
  project_id: 'proj_demo',
  name: 'Demo Kompozisyon',
  format: '16:9',
  width: 1920,
  height: 1080,
  fps: 30,
  scenes: [
    { scene_id: 'scene_01', transition: 'crossfade', transition_duration_seconds: 0.5 },
    { scene_id: 'scene_02', transition: 'cut', transition_duration_seconds: 0 },
    { scene_id: 'scene_03', transition: 'cut', transition_duration_seconds: 0 },
  ],
  text_layers: [
    {
      id: 'opening_title',
      text: 'Kafe Buluşması',
      start_time: 0.25,
      end_time: 2.5,
      anchor: 'top_center',
      x_ratio: 0.5,
      y_ratio: 0.12,
      font_size: 64,
      color: '#FFFFFF',
      background_color: '#000000',
      background_opacity: 0.35,
      fade_in_seconds: 0.25,
      fade_out_seconds: 0.25,
      max_width_ratio: 0.84,
      bold: true,
    },
  ],
  subtitles: {
    enabled: true,
    burn_in: true,
    save_srt: true,
    font_size: 46,
    color: '#FFFFFF',
    background_color: '#000000',
    background_opacity: 0.62,
    margin_bottom_ratio: 0.075,
    max_width_ratio: 0.84,
    max_chars_per_line: 44,
  },
  audio: {
    dialogue_volume_db: 0,
    music_file: null,
    music_volume_db: -20,
    linked: false,
    limiter_enabled: true,
    limiter_limit: 0.95,
  },
  output_format: 'mp4',
};

const baseSummary = {
  composition: baseComposition,
  timeline: [
    {
      scene_id: 'scene_01',
      order: 1,
      duration_seconds: 3,
      start_time: 0,
      end_time: 3,
      transition: 'crossfade',
      transition_duration_seconds: 0.5,
    },
    {
      scene_id: 'scene_02',
      order: 2,
      duration_seconds: 3,
      start_time: 2.5,
      end_time: 5.5,
      transition: 'cut',
      transition_duration_seconds: 0,
    },
    {
      scene_id: 'scene_03',
      order: 3,
      duration_seconds: 2,
      start_time: 5.5,
      end_time: 7.5,
      transition: 'cut',
      transition_duration_seconds: 0,
    },
  ],
  total_duration_seconds: 7.5,
  scene_count: 3,
  text_layer_count: 1,
  transition_count: 1,
  is_saved: true,
};

const completedJob = {
  id: 'render_completed',
  project_id: 'proj_demo',
  status: 'completed',
  progress_percent: 100,
  current_step: 'Completed',
  output_video_path: '/tmp/render_completed.mp4',
  output_metadata: {
    video_file_path: '/tmp/render_completed.mp4',
    file_size_bytes: 1000,
    duration_seconds: 7.5,
    width: 1920,
    height: 1080,
    fps: 30,
    video_codec: 'h264',
    pixel_format: 'yuv420p',
    container: 'mp4',
    frame_count: 225,
    render_duration_seconds: 10,
    engine: 'BLENDER_WORKBENCH',
    composition_name: 'Demo Kompozisyon',
    subtitle_file_path: '/tmp/subtitles.srt',
    subtitle_cue_count: 1,
  },
  error_message: null,
  created_at: '2026-11-04T10:01:00',
  started_at: '2026-11-04T10:01:01',
  completed_at: '2026-11-04T10:02:00',
};

const latestSavedComposition = () => {
  const calls = apiMock.saveProjectComposition.mock.calls;
  return calls[calls.length - 1][1];
};

describe('CompositionStudioPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.listProjects.mockResolvedValue({ items: [project], total: 1, limit: 50, offset: 0 });
    apiMock.getVoiceStatus.mockResolvedValue({
      is_configured: true,
      default_model: 'eleven_multilingual_v2',
      provider: 'ElevenLabs',
    });
    apiMock.getProjectComposition.mockResolvedValue(baseSummary);
    apiMock.listProjectRenders.mockResolvedValue({ items: [], total: 0 });
    apiMock.saveProjectComposition.mockImplementation(async (_projectId: string, composition: any) => ({
      ...baseSummary,
      composition,
      is_saved: true,
    }));
    apiMock.startCompositionRender.mockResolvedValue(completedJob);
    apiMock.getRenderJob.mockResolvedValue(completedJob);
  });

  it('loads a project composition with ordered scenes and Turkish text', async () => {
    render(<CompositionStudioPage />);

    expect(await screen.findByText('Video Kompozisyon Stüdyosu')).toBeInTheDocument();
    await screen.findByTestId('scene-card-scene_01');
    expect(screen.getByDisplayValue('Kafe Buluşması')).toBeInTheDocument();
    expect(screen.getAllByTestId(/^scene-card-/).map((card) => card.getAttribute('data-testid'))).toEqual([
      'scene-card-scene_01',
      'scene-card-scene_02',
      'scene-card-scene_03',
    ]);
    expect(screen.getByText('Merhaba Ayşe!')).toBeInTheDocument();
  });

  it('reorders scenes and saves the new order', async () => {
    const user = userEvent.setup();
    render(<CompositionStudioPage />);
    await screen.findByTestId('scene-card-scene_01');

    await user.click(screen.getByRole('button', { name: "Sahne 1'i aşağı taşı" }));

    expect(screen.getAllByTestId(/^scene-card-/).map((card) => card.getAttribute('data-testid'))).toEqual([
      'scene-card-scene_02',
      'scene-card-scene_01',
      'scene-card-scene_03',
    ]);

    await user.click(screen.getByRole('button', { name: /Kaydet/ }));
    await waitFor(() => expect(apiMock.saveProjectComposition).toHaveBeenCalledTimes(1));

    expect(latestSavedComposition().scenes.map((scene: any) => scene.scene_id)).toEqual([
      'scene_02',
      'scene_01',
      'scene_03',
    ]);
  });

  it('changes a transition and applies a valid transition duration', async () => {
    const user = userEvent.setup();
    render(<CompositionStudioPage />);
    await screen.findByTestId('scene-card-scene_01');

    const transitionSelect = screen.getByLabelText('Sahne 1 geçişi');
    const durationInput = screen.getByLabelText('Sahne 1 geçiş süresi') as HTMLInputElement;

    await user.selectOptions(transitionSelect, 'cut');
    expect(durationInput).toBeDisabled();
    expect(durationInput.value).toBe('0');

    await user.selectOptions(transitionSelect, 'crossfade');
    expect(durationInput).not.toBeDisabled();
    expect(durationInput.value).toBe('0.5');

    await user.click(screen.getByRole('button', { name: /Kaydet/ }));
    await waitFor(() => expect(apiMock.saveProjectComposition).toHaveBeenCalledTimes(1));

    const saved = latestSavedComposition();
    expect(saved.scenes[0].transition).toBe('crossfade');
    expect(saved.scenes[0].transition_duration_seconds).toBe(0.5);
  });

  it('updates subtitle settings and the delivery format', async () => {
    const user = userEvent.setup();
    render(<CompositionStudioPage />);
    await screen.findByTestId('scene-card-scene_01');

    await user.click(screen.getByRole('button', { name: /Dikey 9:16/ }));
    await user.click(screen.getByLabelText('Altyazıları videoya yak'));

    const fontSize = screen.getByLabelText('Altyazı puntosu');
    await user.clear(fontSize);
    await user.type(fontSize, '52');

    await user.click(screen.getByRole('button', { name: /Kaydet/ }));
    await waitFor(() => expect(apiMock.saveProjectComposition).toHaveBeenCalledTimes(1));

    const saved = latestSavedComposition();
    expect(saved.format).toBe('9:16');
    expect(saved.width).toBe(1080);
    expect(saved.height).toBe(1920);
    expect(saved.subtitles.burn_in).toBe(false);
    expect(saved.subtitles.font_size).toBe(52);
  });

  it('starts a render and exposes status, playback and subtitle download', async () => {
    const user = userEvent.setup();
    render(<CompositionStudioPage />);
    await screen.findByTestId('scene-card-scene_01');

    await user.click(screen.getByRole('button', { name: /Render Başlat/ }));

    await waitFor(() => expect(apiMock.startCompositionRender).toHaveBeenCalledTimes(1));
    expect(apiMock.startCompositionRender).toHaveBeenCalledWith(
      'proj_demo',
      expect.objectContaining({ format: '16:9' }),
      expect.objectContaining({ engineOverride: 'BLENDER_WORKBENCH', synthesizeVoices: true })
    );

    expect(await screen.findByText('MP4 indir')).toBeInTheDocument();
    expect(screen.getByText(/SRT indir/)).toBeInTheDocument();
    expect(document.querySelector('video')).toHaveAttribute(
      'src',
      '/api/v1/studio/renders/render_completed/video'
    );
  });
});
