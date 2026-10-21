import { shareURL } from '@tma.js/sdk-react';

import { launch } from '.';

export type ShareResult = 'shared' | 'copied' | 'failed';

/** Поделиться ссылкой: в Telegram — его выбор чата, в PWA — системное «Поделиться», иначе — копирование. */
export async function shareLink(url: string, text: string): Promise<ShareResult> {
  if (launch.mode === 'telegram' && shareURL.isAvailable()) {
    shareURL(url, text);
    return 'shared';
  }
  if (typeof navigator.share === 'function') {
    try {
      await navigator.share({ url, text });
      return 'shared';
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return 'failed'; // передумали
    }
  }
  return copyText(url);
}

export async function copyText(text: string): Promise<ShareResult> {
  try {
    await navigator.clipboard.writeText(text);
    return 'copied';
  } catch {
    return 'failed';
  }
}
