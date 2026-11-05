import { describe, expect, it } from 'vitest';
import {
  isLiveRender,
  isPlayableRender,
  isStalePending,
  workflowState,
} from './studioWorkspace';
import { RenderJob, StudioProject } from '../types/studio';

const NOW = Date.parse('2026-11-05T15:00:00Z');

function job(overrides: Partial<RenderJob> = {}): RenderJob {
  return {
    id: 'render_test',
    project_id: 'proj_test',
    status: 'pending',
    progress_percent: 0,
    current_step: 'Pending',
    created_at: '2026-11-05T14:59:00Z',
    ...overrides,
  } as RenderJob;
}

const project = {
  id: 'proj_test',
  title: 'Test',
  description: '',
  status: 'draft',
  scene_graph: {
    schema_version: '1.0',
    project_id: 'proj_test',
    title: 'Test',
    description: '',
    resolution: { width: 1280, height: 720, aspect_ratio: '16:9', fps: 30 },
    characters: [],
    scenes: [],
  },
  created_at: '2026-11-05T14:00:00Z',
  updated_at: '2026-11-05T14:00:00Z',
} as unknown as StudioProject;

const animationJob = job({
  id: 'render_animation',
  status: 'completed',
  output_metadata: { video_file_path: '/tmp/animation.mp4' } as RenderJob['output_metadata'],
});

describe('stale pending renders', () => {
  it('treats a pending job that never started and is over 30 minutes old as stale', () => {
    const old = job({ created_at: '2026-11-05T14:00:00Z' });
    expect(isStalePending(old, NOW)).toBe(true);
    expect(isLiveRender(old, NOW)).toBe(false);
  });

  it('keeps a freshly dispatched pending job live', () => {
    const fresh = job({ created_at: '2026-11-05T14:59:00Z' });
    expect(isStalePending(fresh, NOW)).toBe(false);
    expect(isLiveRender(fresh, NOW)).toBe(true);
  });

  it('never treats a started or finished job as stale', () => {
    expect(isStalePending(job({ status: 'running', started_at: '2026-11-05T14:00:00Z' }), NOW)).toBe(false);
    expect(isStalePending(job({ status: 'completed' }), NOW)).toBe(false);
  });
});

describe('playable renders', () => {
  it('accepts a completed render with a real file path regardless of engine', () => {
    expect(isPlayableRender(animationJob)).toBe(true);
  });

  it('rejects a completed job that has no file to play', () => {
    expect(isPlayableRender(job({ status: 'completed' }))).toBe(false);
  });

  it('rejects a running job', () => {
    expect(isPlayableRender(job({ status: 'running', output_metadata: { video_file_path: '/tmp/a.mp4' } as RenderJob['output_metadata'] }))).toBe(false);
  });
});

describe('export workflow state', () => {
  const exportState = (renders: RenderJob[]) => {
    const states = workflowState(project, renders, null);
    return states.find((state) => state.id === 'export')!;
  };

  it('is complete once a Blender animation render is playable', () => {
    const state = exportState([animationJob]);
    expect(state.completed).toBe(true);
    expect(state.missing).toEqual([]);
  });

  it('still completes for a finished composition render', () => {
    const compositionJob = job({
      id: 'comp_render',
      status: 'completed',
      output_metadata: { video_file_path: '/tmp/composition.mp4' } as RenderJob['output_metadata'],
    });
    expect(exportState([compositionJob]).completed).toBe(true);
  });

  it('reports the missing render when nothing can be played', () => {
    const state = exportState([job({ status: 'running' })]);
    expect(state.completed).toBe(false);
    expect(state.missing.join(' ')).toContain('Oynatılabilir');
  });
});
