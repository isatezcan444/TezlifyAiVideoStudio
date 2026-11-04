import {
  CompositionTimelineEntry,
  CompositionTransition,
  VideoComposition,
} from '../types/studio';

export interface LocalCompositionTimeline {
  entries: CompositionTimelineEntry[];
  totalDurationSeconds: number;
}

/**
 * Client-side mirror of the backend timeline calculation. It is used for the
 * editor preview only; the backend remains the source of truth when saving and
 * rendering.
 */
export function buildCompositionTimeline(
  composition: VideoComposition,
  sceneDurations: Record<string, number>
): LocalCompositionTimeline {
  const entries: CompositionTimelineEntry[] = [];
  let cursor = 0;

  composition.scenes.forEach((scene, index) => {
    const duration = Number(sceneDurations[scene.scene_id] ?? 0);
    const isLast = index === composition.scenes.length - 1;
    const isClosingFade =
      scene.transition === 'fade_in' || scene.transition === 'fade_out';
    const transition: CompositionTransition =
      isLast && !isClosingFade ? 'cut' : scene.transition;
    const transitionDuration =
      transition === 'cut' ? 0 : Number(scene.transition_duration_seconds || 0);
    const start = cursor;
    const end = start + duration;

    entries.push({
      scene_id: scene.scene_id,
      order: index + 1,
      duration_seconds: duration,
      start_time: round(start),
      end_time: round(end),
      transition,
      transition_duration_seconds: round(transitionDuration),
    });

    cursor = transition === 'crossfade' ? end - transitionDuration : end;
  });

  return {
    entries,
    totalDurationSeconds: round(entries.length ? entries[entries.length - 1].end_time : 0),
  };
}

export function formatCompositionSeconds(seconds: number): string {
  const safe = Math.max(0, Number.isFinite(seconds) ? seconds : 0);
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  return `${minutes}:${remainder.toFixed(1).padStart(4, '0')}`;
}

export const COMPOSITION_FORMAT_DIMENSIONS: Record<
  VideoComposition['format'],
  { width: number; height: number }
> = {
  '16:9': { width: 1920, height: 1080 },
  '9:16': { width: 1080, height: 1920 },
  '1:1': { width: 1080, height: 1080 },
};

export const TRANSITION_LABELS: Record<CompositionTransition, string> = {
  cut: 'Kesme (Cut)',
  fade_in: 'Karartarak Aç (Fade In)',
  fade_out: 'Karartarak Kapat (Fade Out)',
  crossfade: 'Yumuşak Geçiş (Crossfade)',
};

function round(value: number): number {
  return Math.round(value * 1_000_000) / 1_000_000;
}
