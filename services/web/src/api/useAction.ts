import { useState } from 'react';

import { errorText } from '../texts';
import type { Me, Result } from './client';

// Ошибки, после которых экран устарел: состояние надо взять у api заново, а не только показать текст.
const STALE = new Set(['prompt_changed', 'prompt_answered', 'not_ready']);

export function isStale(code: string): boolean {
  return STALE.has(code);
}

export type ActionHandlers = {
  onMe: (me: Me) => void;
  onUnauthorized: () => void;
  onStale: (code: string) => void; // обновить гнездо и сказать, что случилось
};

/**
 * Действия экрана, которые возвращают новое состояние: какое из них сейчас идёт (его кнопка занята),
 * текст ошибки рядом с ним и общие случаи — вход устарел (401) или экран устарел.
 */
export function useAction({ onMe, onUnauthorized, onStale }: ActionHandlers) {
  const [pending, setPending] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function run(key: string, request: Promise<Result<Me>>): Promise<Me | null> {
    setPending(key);
    setMessage(null);
    const result = await request;
    setPending(null);
    if (result.ok) {
      onMe(result.data);
      return result.data;
    }
    if (result.status === 401) onUnauthorized();
    else if (isStale(result.code)) onStale(result.code);
    else setMessage(errorText(result.code));
    return null;
  }

  return { run, pending, busy: pending !== null, message, setMessage };
}
