const MESSAGE_TYPE = 'TEZLIFY_YOUTUBE_CONNECTED';

export function openOAuthPopup(authUrl: string, name: string): Window | null {
  const width = 600;
  const height = 700;
  const left = window.screen.width / 2 - width / 2;
  const top = window.screen.height / 2 - height / 2;
  return window.open(
    authUrl,
    name,
    `width=${width},height=${height},top=${top},left=${left},scrollbars=yes,status=1`
  );
}

/** Resolves when the loopback callback page reports success or failure. */
export function awaitYouTubeOAuth(timeoutMs = 300000): Promise<boolean> {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (success: boolean) => {
      if (settled) return;
      settled = true;
      window.removeEventListener('message', handler);
      resolve(success);
    };
    const handler = (event: MessageEvent) => {
      if (event.data?.type === MESSAGE_TYPE) {
        finish(Boolean(event.data.success));
      }
    };
    window.addEventListener('message', handler);
    window.setTimeout(() => finish(false), timeoutMs);
  });
}

export function isYouTubeOAuthMessage(event: MessageEvent): boolean {
  return event.data?.type === MESSAGE_TYPE;
}
