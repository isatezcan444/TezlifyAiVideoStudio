import { describe, expect, it } from 'vitest';
import { lipSyncLabel } from './ExportStep';
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

const base = {
  width: 1080,
  height: 1920,
  fps: 30,
  video_codec: 'h264',
  duration_seconds: 6.7,
  file_size_bytes: 1_000_000,
  format: '9:16',
};

describe('lipSyncLabel', () => {
  it('names real lip sync only when measured segments were used', () => {
    const label = lipSyncLabel(
      jobWithMetadata({
        ...base,
        lip_sync: {
          real_lip_sync: true,
          speakers_total: 2,
          speakers_aligned: 2,
          scenes: [],
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
          speakers_total: 2,
          speakers_aligned: 0,
          scenes: [],
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
          speakers_total: 3,
          speakers_aligned: 1,
          scenes: [],
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
