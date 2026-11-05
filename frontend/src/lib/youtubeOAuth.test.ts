import { afterEach, describe, expect, it, vi } from 'vitest';
import { awaitYouTubeOAuth, isYouTubeOAuthMessage, openOAuthPopup } from './youtubeOAuth';

function post(data: unknown) {
  window.dispatchEvent(new MessageEvent('message', { data }));
}

describe('youtubeOAuth popup helper', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('resolves true only for a successful loopback callback message', async () => {
    const pending = awaitYouTubeOAuth(1000);

    post({ type: 'SOMETHING_ELSE', success: true });
    post({ type: 'TEZLIFY_YOUTUBE_CONNECTED', success: true });

    await expect(pending).resolves.toBe(true);
  });

  it('resolves false when the user denies the grant', async () => {
    const pending = awaitYouTubeOAuth(1000);

    post({ type: 'TEZLIFY_YOUTUBE_CONNECTED', success: false });

    await expect(pending).resolves.toBe(false);
  });

  it('exposes the message type guard for the accounts page listener', () => {
    expect(
      isYouTubeOAuthMessage(new MessageEvent('message', { data: { type: 'TEZLIFY_YOUTUBE_CONNECTED' } }))
    ).toBe(true);
    expect(isYouTubeOAuthMessage(new MessageEvent('message', { data: { type: 'OTHER' } }))).toBe(false);
  });

  it('opens the authorization URL in a sized popup', () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null);

    openOAuthPopup('https://accounts.google.test/auth', 'tezlify_grant_conn_1_upload');

    expect(open).toHaveBeenCalledWith(
      'https://accounts.google.test/auth',
      'tezlify_grant_conn_1_upload',
      expect.stringContaining('width=600')
    );
  });
});
