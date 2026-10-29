/**
 * Вход вне Telegram: токен сессии PWA и (с DEBUG) подставной пользователь.
 * Живут в localStorage; в приватном режиме браузера не сохраняются — тогда вход нужен каждый раз.
 */
const TOKEN = 'gnezdo.session';
const DEBUG_USER = 'gnezdo.debugUser';
const PENDING_LOGIN = 'gnezdo.pendingLogin';
// Вход ждёт подтверждения в боте. iOS может выгрузить PWA, пока человек в Telegram, — после возврата
// ждём тот же вход, а не начинаем новый. Nonce в api живёт 10 минут.
const PENDING_TTL_MS = 10 * 60_000;

export type PendingLogin = { nonce: string; link: string };

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // приватный режим: просто не запомним
  }
}

export const credentials = {
  token: () => read(TOKEN),
  setToken: (token: string) => write(TOKEN, token),
  debugUser: (): number | null => {
    const value = read(DEBUG_USER);
    return value === null ? null : Number(value);
  },
  setDebugUser: (id: number) => write(DEBUG_USER, String(id)),
  pendingLogin: (): PendingLogin | null => {
    try {
      const saved = JSON.parse(read(PENDING_LOGIN) ?? 'null') as (PendingLogin & { at: number }) | null;
      return saved && Date.now() - saved.at < PENDING_TTL_MS ? { nonce: saved.nonce, link: saved.link } : null;
    } catch {
      return null;
    }
  },
  setPendingLogin: (login: PendingLogin | null) =>
    write(PENDING_LOGIN, login ? JSON.stringify({ nonce: login.nonce, link: login.link, at: Date.now() }) : null),
  clear: () => {
    write(TOKEN, null);
    write(DEBUG_USER, null);
    write(PENDING_LOGIN, null);
  },
};
