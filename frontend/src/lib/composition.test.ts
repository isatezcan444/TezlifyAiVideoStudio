import { describe, expect, it } from 'vitest';
import {
  buildCompositionTimeline,
  COMPOSITION_FORMAT_DIMENSIONS,
  formatCompositionSeconds,
} from './composition';
import { VideoComposition } from '../types/studio';

const composition: VideoComposition = {
  id: 'comp_test',
  project_id: 'proj_test',
  name: 'Test',
  format: '16:9',
  width: 1920,
  height: 1080,
  fps: 30,
  scenes: [
    { scene_id: 'scene_01', transition: 'crossfade', transition_duration_seconds: 0.5 },
    { scene_id: 'scene_02', transition: 'cut', transition_duration_seconds: 0 },
    { scene_id: 'scene_03', transition: 'fade_out', transition_duration_seconds: 0.4 },
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

describe('buildCompositionTimeline', () => {
  it('subtracts crossfade overlap and keeps sequential transitions sequential', () => {
    const timeline = buildCompositionTimeline(composition, {
      scene_01: 4,
      scene_02: 3,
      scene_03: 2,
    });

    expect(timeline.entries.map((entry) => [entry.scene_id, entry.start_time, entry.end_time])).toEqual([
      ['scene_01', 0, 4],
      ['scene_02', 3.5, 6.5],
      ['scene_03', 6.5, 8.5],
    ]);
    expect(timeline.totalDurationSeconds).toBe(8.5);
  });

  it('treats a dangling crossfade on the final scene as a cut', () => {
    const withDanglingCrossfade: VideoComposition = {
      ...composition,
      scenes: [
        { scene_id: 'scene_01', transition: 'crossfade', transition_duration_seconds: 0.5 },
        { scene_id: 'scene_02', transition: 'crossfade', transition_duration_seconds: 0.5 },
      ],
    };

    const timeline = buildCompositionTimeline(withDanglingCrossfade, {
      scene_01: 4,
      scene_02: 3,
      scene_03: 2,
    });

    expect(timeline.entries[1].transition).toBe('cut');
    expect(timeline.entries[1].transition_duration_seconds).toBe(0);
    expect(timeline.totalDurationSeconds).toBe(6.5);
  });

  it('exposes all three delivery dimensions', () => {
    expect(COMPOSITION_FORMAT_DIMENSIONS['16:9']).toEqual({ width: 1920, height: 1080 });
    expect(COMPOSITION_FORMAT_DIMENSIONS['9:16']).toEqual({ width: 1080, height: 1920 });
    expect(COMPOSITION_FORMAT_DIMENSIONS['1:1']).toEqual({ width: 1080, height: 1080 });
  });

  it('formats durations for the editor preview', () => {
    expect(formatCompositionSeconds(0)).toBe('0:00.0');
    expect(formatCompositionSeconds(7.5)).toBe('0:07.5');
    expect(formatCompositionSeconds(65.2)).toBe('1:05.2');
  });
});
