import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { StudioWorkspacePage } from './StudioWorkspacePage';

const apiMock = vi.hoisted(() => ({
  listProjects: vi.fn(),
  listRenderJobs: vi.fn(),
  listCharacters: vi.fn(),
  listVoices: vi.fn(),
  getVoiceStatus: vi.fn(),
  getProjectComposition: vi.fn(),
  createProject: vi.fn(),
  updateProject: vi.fn(),
  generateStory: vi.fn(),
  deleteProject: vi.fn(),
  createCharacter: vi.fn(),
  updateCharacter: vi.fn(),
  listProjectRenders: vi.fn(),
  saveProjectComposition: vi.fn(),
  startCompositionRender: vi.fn(),
  startProjectRender: vi.fn(),
  getRenderJob: vi.fn(),
  getRenderVideoUrl: vi.fn((jobId: string) => `/api/v1/studio/renders/${jobId}/video`),
  getRenderSubtitlesUrl: vi.fn((jobId: string) => `/api/v1/studio/renders/${jobId}/subtitles`),
}));

vi.mock('../services/api', () => ({ apiService: apiMock }));

const sceneGraph = {
  schema_version: '1.0',
  project_id: 'proj_demo',
  title: 'Ali ve Ayşe Kafe Buluşması',
  description: 'Kısa bir kafe hikâyesi',
  resolution: { width: 1920, height: 1080, aspect_ratio: '16:9', fps: 30 },
  characters: [
    {
      id: 'char_ali',
      name: 'Ali',
      voice_id: 'voice_ali',
      style: {
        hair_color: '#2C1810',
        skin_tone: '#F5D0A9',
        shirt_color: '#3B82F6',
        pants_color: '#1E293B',
      },
    },
    {
      id: 'char_ayse',
      name: 'Ayşe',
      voice_id: 'voice_ayse',
      style: {
        hair_color: '#4A2C1A',
        skin_tone: '#F1C27D',
        shirt_color: '#EC4899',
        pants_color: '#334155',
      },
    },
  ],
  scenes: [
    {
      scene_id: 'scene_01',
      sequence_order: 1,
      duration_seconds: 5,
      background: { type: 'preset', asset_id: 'bg_modern_cafe', lighting: 'warm_interior' },
      camera: { angle: 'two_shot', fov: 45, movement: 'static' },
      character_placements: [
        {
          character_id: 'char_ali',
          position: [-0.7, 0, 0],
          rotation_y: 25,
          pose: 'standing',
          expression: 'neutral',
        },
      ],
      dialogues: [
        {
          character_id: 'char_ali',
          start_time: 0.5,
          end_time: 2.5,
          text: 'Merhaba Ayşe, nasılsın?',
          audio_file: null,
          visemes: [],
        },
      ],
      transition: { type: 'cut', duration_seconds: 0 },
    },
    {
      scene_id: 'scene_02',
      sequence_order: 2,
      duration_seconds: 4,
      background: { type: 'preset', asset_id: 'bg_modern_cafe', lighting: 'warm_interior' },
      camera: { angle: 'medium_shot', fov: 45, movement: 'static' },
      character_placements: [
        {
          character_id: 'char_ayse',
          position: [0.7, 0, 0],
          rotation_y: -25,
          pose: 'standing',
          expression: 'happy',
        },
      ],
      dialogues: [
        {
          character_id: 'char_ayse',
          start_time: 0.5,
          end_time: 2.5,
          text: 'İyiyim, teşekkürler!',
          audio_file: '/tmp/ayse.mp3',
          visemes: [],
        },
      ],
      transition: { type: 'cut', duration_seconds: 0 },
    },
  ],
};

const project = {
  id: 'proj_demo',
  title: 'Ali ve Ayşe Kafe Buluşması',
  description: 'Kısa bir kafe hikâyesi',
  status: 'scenario_ready',
  scene_graph: sceneGraph,
  total_duration_seconds: 9,
  scene_count: 2,
  character_count: 2,
  created_at: '2026-11-04T10:00:00',
  updated_at: '2026-11-04T10:15:00',
};

const composition = {
  id: 'comp_proj_demo',
  project_id: 'proj_demo',
  name: 'Demo Kompozisyon',
  format: '16:9',
  width: 1920,
  height: 1080,
  fps: 30,
  scenes: [
    { scene_id: 'scene_01', transition: 'cut', transition_duration_seconds: 0 },
    { scene_id: 'scene_02', transition: 'cut', transition_duration_seconds: 0 },
  ],
  text_layers: [],
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
    limiter_enabled: true,
    limiter_limit: 0.95,
  },
  output_format: 'mp4',
};

const compositionSummary = {
  composition,
  timeline: [
    {
      scene_id: 'scene_01',
      order: 1,
      duration_seconds: 5,
      start_time: 0,
      end_time: 5,
      transition: 'cut',
      transition_duration_seconds: 0,
    },
    {
      scene_id: 'scene_02',
      order: 2,
      duration_seconds: 4,
      start_time: 5,
      end_time: 9,
      transition: 'cut',
      transition_duration_seconds: 0,
    },
  ],
  total_duration_seconds: 9,
  scene_count: 2,
  text_layer_count: 0,
  transition_count: 0,
  is_saved: true,
};

const completedCompositionJob = {
  id: 'comp_render_completed',
  project_id: 'proj_demo',
  status: 'completed',
  progress_percent: 100,
  current_step: 'Completed',
  output_video_path: '/tmp/composition.mp4',
  output_metadata: {
    video_file_path: '/tmp/composition.mp4',
    file_size_bytes: 1024,
    duration_seconds: 9,
    width: 1920,
    height: 1080,
    fps: 30,
    video_codec: 'h264',
    pixel_format: 'yuv420p',
    container: 'mp4',
    frame_count: 270,
    render_duration_seconds: 12,
    engine: 'FFMPEG_COMPOSITION',
    composition_name: 'Demo Kompozisyon',
    format: '16:9',
    subtitle_file_path: '/tmp/subtitles.srt',
    subtitle_cue_count: 2,
  },
  error_message: null,
  created_at: '2026-11-04T10:20:00',
  started_at: '2026-11-04T10:20:01',
  completed_at: '2026-11-04T10:21:00',
};

const failedAnimationJob = {
  id: 'render_failed_animation',
  project_id: 'proj_demo',
  status: 'failed',
  progress_percent: 42,
  current_step: 'Animation render failed',
  output_video_path: null,
  output_metadata: null,
  error_message: 'Blender scene_02 render failed: GPU timeout',
  created_at: '2026-11-04T10:05:00',
  started_at: '2026-11-04T10:05:01',
  completed_at: '2026-11-04T10:06:00',
};

const voices = [
  {
    voice_id: 'voice_ali',
    name: 'Ali Sesi',
    gender: 'male',
    language: 'tr',
    category: 'premade',
    preview_url: null,
    description: 'Test sesi',
  },
  {
    voice_id: 'voice_ayse',
    name: 'Ayşe Sesi',
    gender: 'female',
    language: 'tr',
    category: 'premade',
    preview_url: null,
    description: 'Test sesi',
  },
];

const library = [
  {
    id: 'char_ali',
    name: 'Ali',
    description: 'Kafe sahibi',
    gender: 'male',
    palette: {
      skin_tone: '#F5D0A9',
      hair_color: '#2C1810',
      eye_color: '#3B2416',
      shirt_color: '#3B82F6',
      pants_color: '#1E293B',
      shoes_color: '#111827',
    },
    hair_style: 'short',
    eye_style: 'round',
    clothing_style: 'casual',
    voice_id: 'voice_ali',
    default_expression: 'neutral',
    default_pose: 'standing',
    proportions: {
      head_scale: 1,
      torso_length: 1,
      arm_length: 1,
      leg_length: 1,
      shoulder_width: 1,
    },
    blend_file_path: null,
    thumbnail_path: null,
    is_builtin: true,
    created_at: '2026-11-04T09:00:00',
    updated_at: '2026-11-04T09:00:00',
  },
];

function setupDefaultMocks() {
  apiMock.listProjects.mockResolvedValue({ items: [project], total: 1, limit: 100, offset: 0 });
  apiMock.listRenderJobs.mockResolvedValue({
    items: [completedCompositionJob, failedAnimationJob],
    total: 2,
  });
  apiMock.listCharacters.mockResolvedValue({ items: library, total: 1, limit: 100, offset: 0 });
  apiMock.listVoices.mockResolvedValue({ items: voices, total: 2, is_configured: false });
  apiMock.getVoiceStatus.mockResolvedValue({
    is_configured: false,
    default_model: 'eleven_multilingual_v2',
    provider: 'ElevenLabs',
  });
  apiMock.getProjectComposition.mockResolvedValue(compositionSummary);
  apiMock.listProjectRenders.mockResolvedValue({
    items: [completedCompositionJob, failedAnimationJob],
    total: 2,
  });
  apiMock.updateProject.mockImplementation(async (_id: string, data: any) => ({
    ...project,
    ...data,
    scene_graph: data.scene_graph || project.scene_graph,
  }));
  apiMock.generateStory.mockResolvedValue({
    scene_graph: { ...sceneGraph, title: 'Yeni Hikâye' },
    total_duration_seconds: 9,
    scene_count: 2,
    character_count: 2,
  });
  apiMock.createProject.mockResolvedValue({
    ...project,
    id: 'proj_new',
    title: 'Yeni Proje',
    scene_graph: { ...sceneGraph, project_id: 'proj_new', title: 'Yeni Proje' },
  });
  apiMock.deleteProject.mockResolvedValue({ id: 'proj_demo', deleted: true, archived: false });
  apiMock.createCharacter.mockResolvedValue(library[0]);
  apiMock.updateCharacter.mockImplementation(async (id: string, data: any) => ({
    ...library[0],
    id,
    ...data,
    palette: data.palette || library[0].palette,
  }));
  apiMock.saveProjectComposition.mockImplementation(async (_id: string, next: any) => ({
    ...compositionSummary,
    composition: next,
  }));
  apiMock.startCompositionRender.mockResolvedValue(completedCompositionJob);
  apiMock.startProjectRender.mockResolvedValue(failedAnimationJob);
  apiMock.getRenderJob.mockResolvedValue(failedAnimationJob);
}

async function openWorkflow() {
  const user = userEvent.setup();
  render(
    <StudioWorkspacePage
      onOpenMediaLibrary={vi.fn()}
      onOpenCharacterStudio={vi.fn()}
    />
  );
  await screen.findByText('Fikirden yayına, tek bir üretim akışı');
  await user.click(screen.getByRole('button', { name: 'Projeler' }));
  await screen.findByText('Ali ve Ayşe Kafe Buluşması');
  await user.click(screen.getAllByRole('button', { name: /Düzenle/i })[0]);
  await screen.findByRole('button', { name: /1\. Proje/i });
  return user;
}

describe('StudioWorkspacePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    setupDefaultMocks();
  });

  it('dashboard uses real project and render data', async () => {
    render(
      <StudioWorkspacePage
        onOpenMediaLibrary={vi.fn()}
        onOpenCharacterStudio={vi.fn()}
      />
    );

    expect(await screen.findByText('Fikirden yayına, tek bir üretim akışı')).toBeInTheDocument();
    expect(screen.getByText('Toplam proje')).toBeInTheDocument();
    expect(screen.getByText('Tamamlanan render')).toBeInTheDocument();
    expect(screen.getAllByText('Ali ve Ayşe Kafe Buluşması').length).toBeGreaterThan(0);
    expect(screen.getByText(/1 video/)).toBeInTheDocument();
    expect(screen.getByText('Render durumu')).toBeInTheDocument();
  });

  it('creates a project from the dashboard and opens the workflow', async () => {
    const user = userEvent.setup();
    render(
      <StudioWorkspacePage
        onOpenMediaLibrary={vi.fn()}
        onOpenCharacterStudio={vi.fn()}
      />
    );

    await screen.findByText('Fikirden yayına, tek bir üretim akışı');
    await user.click(screen.getAllByRole('button', { name: /Yeni proje/i })[0]);
    const titleInput = screen.getByLabelText('Proje adı');
    await user.clear(titleInput);
    await user.type(titleInput, 'Yeni Proje');
    await user.click(screen.getByRole('button', { name: /Projeyi Oluştur/i }));

    await waitFor(() => expect(apiMock.createProject).toHaveBeenCalled());
    expect(apiMock.createProject.mock.calls[0][0]).toMatchObject({ title: 'Yeni Proje' });
    expect(await screen.findByRole('button', { name: /1\. Proje/i })).toBeInTheDocument();
  });

  it('edits project metadata from project cards', async () => {
    const user = userEvent.setup();
    render(
      <StudioWorkspacePage
        onOpenMediaLibrary={vi.fn()}
        onOpenCharacterStudio={vi.fn()}
      />
    );

    await screen.findByText('Fikirden yayına, tek bir üretim akışı');
    await user.click(screen.getByRole('button', { name: 'Projeler' }));
    await user.click(
      await screen.findByRole('button', { name: 'Ali ve Ayşe Kafe Buluşması projesini düzenle' })
    );
    const titleInput = screen.getByLabelText('Proje adı');
    await user.clear(titleInput);
    await user.type(titleInput, 'Güncel Proje');
    await user.click(screen.getByRole('button', { name: /Değişiklikleri Kaydet/i }));

    await waitFor(() =>
      expect(apiMock.updateProject).toHaveBeenCalledWith(
        'proj_demo',
        expect.objectContaining({ title: 'Güncel Proje' })
      )
    );
  });

  it('shows workflow completion states and generates a story through the real endpoint wrapper', async () => {
    const user = await openWorkflow();
    await user.click(screen.getByRole('button', { name: /2\. Hikâye/i }));
    expect(await screen.findByText('Hikâye ve senaryo')).toBeInTheDocument();
    expect(screen.getByText('Hikâye hazır')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Yeni hikâye üret/i }));
    await waitFor(() => expect(apiMock.generateStory).toHaveBeenCalled());
    expect(apiMock.generateStory.mock.calls[0][0]).toMatchObject({
      prompt: expect.any(String),
      aspect_ratio: '16:9',
    });
    await waitFor(() =>
      expect(apiMock.updateProject).toHaveBeenCalledWith(
        'proj_demo',
        expect.objectContaining({
          scene_graph: expect.objectContaining({ title: 'Yeni Hikâye' }),
        })
      )
    );
  });

  it('reorders scenes, edits dialogue text and saves the SceneGraph', async () => {
    const user = await openWorkflow();
    await user.click(screen.getByRole('button', { name: /4\. Sahneler/i }));
    expect(await screen.findByText('Sahne editörü')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'scene_01 sahnesini aşağı taşı' }));
    const dialogueInput = screen.getByDisplayValue('Merhaba Ayşe, nasılsın?');
    await user.clear(dialogueInput);
    await user.type(dialogueInput, 'Selam Ayşe!');
    await user.click(screen.getByRole('button', { name: /^Kaydet$/i }));

    await waitFor(() => expect(apiMock.updateProject).toHaveBeenCalled());
    const payload = apiMock.updateProject.mock.calls[apiMock.updateProject.mock.calls.length - 1][1];
    expect(payload.scene_graph.scenes[0].scene_id).toBe('scene_02');
    expect(
      payload.scene_graph.scenes
        .flatMap((scene: any) => scene.dialogues)
        .some((dialogue: any) => dialogue.text === 'Selam Ayşe!')
    ).toBe(true);
  });

  it('manages project cast voice profiles and shows the real voice source state', async () => {
    const user = await openWorkflow();
    await user.click(screen.getByRole('button', { name: /3\. Karakterler/i }));
    expect(await screen.findByText('Karakterler ve ses profilleri')).toBeInTheDocument();
    expect(screen.getByText(/ElevenLabs yapılandırılmadı/)).toBeInTheDocument();
    expect(screen.queryByText('ElevenLabs bağlı')).not.toBeInTheDocument();

    const aliCard = screen.getByText('Ali').closest('article')!;
    const voiceSelect = within(aliCard).getByRole('combobox');
    await user.selectOptions(voiceSelect, 'voice_ayse');
    await waitFor(() => expect(apiMock.updateProject).toHaveBeenCalled());
  });

  it('edits a project character and keeps the library copy in sync', async () => {
    const user = await openWorkflow();
    await user.click(screen.getByRole('button', { name: /3\. Karakterler/i }));
    await user.click(screen.getByRole('button', { name: 'Ali karakterini düzenle' }));

    const nameInput = screen.getByLabelText('Karakter adı');
    await user.clear(nameInput);
    await user.type(nameInput, 'Ali Veli');
    await user.click(screen.getByRole('button', { name: /Karakteri kaydet/i }));

    await waitFor(() =>
      expect(apiMock.updateCharacter).toHaveBeenCalledWith(
        'char_ali',
        expect.objectContaining({ name: 'Ali Veli' })
      )
    );
    await waitFor(() => expect(apiMock.updateProject).toHaveBeenCalled());
    const payload = apiMock.updateProject.mock.calls[apiMock.updateProject.mock.calls.length - 1][1];
    expect(
      payload.scene_graph.characters.some((character: any) => character.name === 'Ali Veli')
    ).toBe(true);
  });

  it('shows failed render state with collapsible technical details', async () => {
    const user = await openWorkflow();
    await user.click(screen.getByRole('button', { name: /5\. Animasyon/i }));
    expect(await screen.findByText('Animasyon ve Blender render')).toBeInTheDocument();
    expect(screen.getByText('Başarısız')).toBeInTheDocument();
    expect(screen.getByText('Teknik hata ayrıntısı')).toBeInTheDocument();
    expect(screen.getByText(/GPU timeout/)).toBeInTheDocument();
  });

  it('embeds the existing composition studio for the selected project', async () => {
    const user = await openWorkflow();
    await user.click(screen.getByRole('button', { name: /6\. Kompozisyon/i }));

    expect(await screen.findByText('Kompozisyon ayarları')).toBeInTheDocument();
    expect(screen.getByText('Sahne Sırası ve Geçişler')).toBeInTheDocument();
    expect(screen.getByText('Türkçe Altyazılar')).toBeInTheDocument();
    expect(screen.queryByLabelText('Proje seçimi')).not.toBeInTheDocument();
  });

  it('shows completed exports with MP4 and SRT actions', async () => {
    const user = await openWorkflow();
    await user.click(screen.getByRole('button', { name: /7\. Dışa Aktar/i }));

    expect(await screen.findByText('Dışa aktar')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /MP4 indir/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /SRT indir/i })).toBeInTheDocument();
    expect(screen.getByText('1920 × 1080')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Projeye geri dön/i })).toBeInTheDocument();
  });

  it('renders the workspace at a mobile viewport without removing controls', async () => {
    window.innerWidth = 375;
    render(
      <StudioWorkspacePage
        onOpenMediaLibrary={vi.fn()}
        onOpenCharacterStudio={vi.fn()}
      />
    );

    expect(await screen.findByText('Fikirden yayına, tek bir üretim akışı')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Genel Bakış' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Projeler' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Üretim Akışı' })).toBeInTheDocument();
  });

  it('surfaces API errors without fake fallback statistics', async () => {
    apiMock.listProjects.mockRejectedValue(new Error('Backend erişilemiyor.'));
    render(
      <StudioWorkspacePage
        onOpenMediaLibrary={vi.fn()}
        onOpenCharacterStudio={vi.fn()}
      />
    );

    expect(await screen.findByText('Studio verisi alınamadı')).toBeInTheDocument();
    expect(screen.getByText('Backend erişilemiyor.')).toBeInTheDocument();
    expect(screen.queryByText('Fikirden yayına, tek bir üretim akışı')).not.toBeInTheDocument();
  });
});
