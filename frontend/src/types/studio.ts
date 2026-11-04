export interface CharacterColorPalette {
  skin_tone: string;
  hair_color: string;
  eye_color: string;
  shirt_color: string;
  pants_color: string;
  shoes_color: string;
}

export interface BodyProportions {
  head_scale: number;
  torso_length: number;
  arm_length: number;
  leg_length: number;
  shoulder_width: number;
}

export interface Character {
  id: string;
  name: string;
  description: string;
  gender: 'male' | 'female' | 'neutral';
  palette: CharacterColorPalette;
  hair_style: string;
  eye_style: string;
  clothing_style: string;
  voice_id: string;
  default_expression: string;
  default_pose: string;
  proportions: BodyProportions;
  blend_file_path?: string | null;
  thumbnail_path?: string | null;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

export interface CharacterListResponse {
  items: Character[];
  total: number;
  limit: number;
  offset: number;
}

export interface StudioAsset {
  id: string;
  name: string;
  category: 'background' | 'prop' | 'lighting';
  description: string;
  file_path: string;
  asset_format: string;
  thumbnail_path?: string | null;
  version: string;
  tags: string[];
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

export interface StudioAssetListResponse {
  items: StudioAsset[];
  total: number;
  limit: number;
  offset: number;
}

export interface RenderJob {
  id: string;
  project_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress_percent: number;
  current_step: string;
  output_video_path?: string | null;
  output_metadata?: {
    video_file_path?: string;
    file_size_bytes: number;
    duration_seconds: number;
    width: number;
    height: number;
    fps: number;
    video_codec: string;
    pixel_format: string;
    container: string;
    frame_count: number;
    render_duration_seconds: number;
    engine: string;
    composition_id?: string | null;
    composition_name?: string | null;
    format?: string | null;
    subtitle_file_path?: string | null;
    subtitle_cue_count?: number;
    text_layer_count?: number;
    transition_count?: number;
    scene_count?: number;
    lip_sync?: {
      real_lip_sync: boolean;
      speakers_total: number;
      speakers_aligned: number;
      scenes: Array<{
        scene_id: string;
        speakers: Record<string, string>;
        real_lip_sync: boolean;
      }>;
    } | null;
  } | null;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface RenderJobListResponse {
  items: RenderJob[];
  total: number;
}

export interface SceneGraphCharacterStyle {
  hair_color: string;
  skin_tone: string;
  shirt_color: string;
  pants_color: string;
}

export interface SceneGraphCharacter {
  id: string;
  name: string;
  voice_id: string;
  style: SceneGraphCharacterStyle;
}

export interface SceneGraphPlacement {
  character_id: string;
  position: [number, number, number];
  rotation_y: number;
  pose: string;
  expression: string;
}

export interface SceneGraphDialogue {
  character_id: string;
  start_time: number;
  end_time: number;
  text: string;
  audio_file?: string | null;
  visemes?: Array<{ time: number; shape: string }>;
}

export interface SceneGraphScene {
  scene_id: string;
  sequence_order: number;
  duration_seconds: number;
  background: {
    type: 'preset' | 'color' | 'custom';
    asset_id: string;
    lighting: string;
  };
  camera: {
    angle: string;
    fov: number;
    movement: string;
  };
  character_placements: SceneGraphPlacement[];
  dialogues: SceneGraphDialogue[];
  transition?: { type: string; duration_seconds: number } | null;
}

export interface SceneGraph {
  schema_version: string;
  project_id: string;
  title: string;
  description: string;
  resolution: {
    width: number;
    height: number;
    aspect_ratio: '16:9' | '9:16' | '1:1';
    fps: number;
  };
  characters: SceneGraphCharacter[];
  scenes: SceneGraphScene[];
}

export interface GenerateStoryResponse {
  scene_graph: SceneGraph;
  total_duration_seconds: number;
  scene_count: number;
  character_count: number;
}

export interface StudioProject {
  id: string;
  title: string;
  description: string;
  status: string;
  scene_graph?: SceneGraph | null;
  total_duration_seconds: number;
  scene_count: number;
  character_count: number;
  created_at: string;
  updated_at: string;
}

export interface StudioProjectListResponse {
  items: StudioProject[];
  total: number;
  limit: number;
  offset: number;
}

export interface VoiceProfile {
  voice_id: string;
  name: string;
  gender: string;
  language: string;
  category: string;
  preview_url?: string | null;
  description?: string | null;
}

export interface VoiceListResponse {
  items: VoiceProfile[];
  total: number;
  is_configured: boolean;
}

export interface VoiceStatusResponse {
  is_configured: boolean;
  default_model: string;
  provider: string;
}

// --- Video Composition Studio (Stage 4.5) ---

export type CompositionFormat = '16:9' | '9:16' | '1:1';

export type CompositionTransition = 'cut' | 'fade_in' | 'fade_out' | 'crossfade';

export type CompositionTextAnchor =
  | 'top_left'
  | 'top_center'
  | 'top_right'
  | 'center_left'
  | 'center'
  | 'center_right'
  | 'bottom_left'
  | 'bottom_center'
  | 'bottom_right';

export interface CompositionScene {
  scene_id: string;
  transition: CompositionTransition;
  transition_duration_seconds: number;
}

export interface CompositionTextLayer {
  id: string;
  text: string;
  start_time: number;
  end_time: number;
  anchor: CompositionTextAnchor;
  x_ratio: number;
  y_ratio: number;
  font_size: number;
  color: string;
  background_color: string | null;
  background_opacity: number;
  fade_in_seconds: number;
  fade_out_seconds: number;
  max_width_ratio: number;
  bold: boolean;
}

export interface CompositionSubtitleSettings {
  enabled: boolean;
  burn_in: boolean;
  save_srt: boolean;
  font_size: number;
  color: string;
  background_color: string;
  background_opacity: number;
  margin_bottom_ratio: number;
  max_width_ratio: number;
  max_chars_per_line: number;
}

export interface CompositionAudioSettings {
  dialogue_volume_db: number;
  music_file: string | null;
  music_volume_db: number;
  limiter_enabled: boolean;
  limiter_limit: number;
}

export interface VideoComposition {
  id: string;
  project_id: string;
  name: string;
  format: CompositionFormat;
  width: number;
  height: number;
  fps: number;
  scenes: CompositionScene[];
  text_layers: CompositionTextLayer[];
  subtitles: CompositionSubtitleSettings;
  audio: CompositionAudioSettings;
  output_format: 'mp4';
}

export interface CompositionTimelineEntry {
  scene_id: string;
  order: number;
  duration_seconds: number;
  start_time: number;
  end_time: number;
  transition: CompositionTransition;
  transition_duration_seconds: number;
}

export interface CompositionSummary {
  composition: VideoComposition;
  timeline: CompositionTimelineEntry[];
  total_duration_seconds: number;
  scene_count: number;
  text_layer_count: number;
  transition_count: number;
  is_saved: boolean;
}



