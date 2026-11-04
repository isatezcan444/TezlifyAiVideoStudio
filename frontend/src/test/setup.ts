import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// jsdom does not implement media playback. These stubs keep <video> playback
// assertions deterministic without affecting component behaviour.
Object.defineProperty(HTMLMediaElement.prototype, 'play', {
  configurable: true,
  value: vi.fn().mockResolvedValue(undefined),
});
Object.defineProperty(HTMLMediaElement.prototype, 'pause', {
  configurable: true,
  value: vi.fn(),
});

// jsdom does not implement scrolling. The workflow scrolls to the top when a
// step changes, so keep that behaviour safe and silent in tests.
Object.defineProperty(window, 'scrollTo', {
  configurable: true,
  value: vi.fn(),
});
