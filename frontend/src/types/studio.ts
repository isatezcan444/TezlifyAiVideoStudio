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

export interface StudioProject {
  id: string;
  title: string;
  description: string;
  status: string;
  scene_graph?: any;
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


