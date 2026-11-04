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
