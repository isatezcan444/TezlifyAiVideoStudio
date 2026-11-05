import { describe, expect, it } from 'vitest';
import { audioLabel, lipSyncLabel } from './ExportStep';
import { RenderJob } from '../../../types/studio';

function jobWithMetadata(metadata: RenderJob['output_metadata']): RenderJob {
  return {
    job_id: 'job_1',
    project_id: 'proj_1',
    job_type: 'COMPOSITION',
    status: 'COMPLETED',
    progress_percent: 100,
    current_step: 'done',
    output_metadata: metadata,
    created_at: '2026-11-05T00:00:00Z',
  } as unknown as RenderJob;
}

// Every required field of RenderJob['output_metadata']. The previous fixture
// omitted five of them, which made `tsc` fail while vitest still passed because
// vitest does not typecheck.
const base = {
  width: 1080,
  height: 1920,
  fps: 30,
  video_codec: 'h264',
  pixel_format: 'yuv420p',
  container: 'mp4',
  frame_count: 201,
  render_duration_seconds: 42.5,
  engine: 'BLENDER_EEVEE',
  duration_seconds: 6.7,
  file_size_bytes: 1_000_000,
  format: '9:16' as const,
};

describe('lipSyncLabel', () => {
  const speaker = (mode: 'viseme' | 'legacy_flap') => ({ mode, segments: 12, keyframes: 24 });

  it('names real lip sync only when measured segments were used', () => {
    const label = lipSyncLabel(
      jobWithMetadata({
        ...base,
        lip_sync: {
          real_lip_sync: true,
          scenes: [
            {
              scene_id: 'scene_a',
              real_lip_sync: true,
              speakers: { char_ali: speaker('viseme'), char_ayse: speaker('viseme') },
            },
          ],
        },
      }).output_metadata
    );
    expect(label).toContain('Gerçek lip-sync');
    expect(label).toContain('2/2');
  });

  it('never claims real lip sync when every speaker fell back', () => {
    const label = lipSyncLabel(
      jobWithMetadata({
        ...base,
        lip_sync: {
          real_lip_sync: false,
          scenes: [
            {
              scene_id: 'scene_a',
              real_lip_sync: false,
              speakers: { char_ali: speaker('legacy_flap'), char_ayse: speaker('legacy_flap') },
            },
          ],
        },
      }).output_metadata
    );
    expect(label).not.toContain('Gerçek Lip-Sync');
    expect(label).not.toContain('Gerçek lip-sync');
    expect(label).toContain('Basit ağız animasyonu');
  });

  it('reports partial alignment as partial rather than as success', () => {
    const label = lipSyncLabel(
      jobWithMetadata({
        ...base,
        lip_sync: {
          real_lip_sync: true,
          scenes: [
            {
              scene_id: 'scene_a',
              real_lip_sync: true,
              speakers: { char_ali: speaker('viseme') },
            },
            {
              scene_id: 'scene_b',
              real_lip_sync: false,
              speakers: { char_ali: speaker('legacy_flap'), char_ayse: speaker('legacy_flap') },
            },
          ],
        },
      }).output_metadata
    );
    expect(label).toContain('1/3');
  });

  it('says so when a render predates lip-sync metadata', () => {
    expect(lipSyncLabel({ ...base })).toContain('Eski render');
    expect(lipSyncLabel(null)).toContain('Eski render');
    expect(lipSyncLabel(undefined)).toContain('Eski render');
  });
});

describe('audioLabel', () => {
  it('says the video is silent when loudness was measured as silence', () => {
    const label = audioLabel({ ...base, audio_audible: false, audio_mean_db: -91.0, audio_max_db: -91.0 });
    expect(label).toContain('Sessiz');
    expect(label).not.toContain('Sesli');
  });

  it('reports audible sound with the measured level', () => {
    const label = audioLabel({ ...base, audio_audible: true, audio_mean_db: -21.8, audio_max_db: -5.9 });
    expect(label).toContain('Sesli');
    expect(label).toContain('-22');
  });

  it('does not guess for renders that predate the measurement', () => {
    expect(audioLabel({ ...base })).toContain('ölçülmedi');
    expect(audioLabel(null)).toContain('ölçülmedi');
    expect(audioLabel({ ...base, has_audio: false })).toContain('Ses yok');
  });
});
