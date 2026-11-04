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
