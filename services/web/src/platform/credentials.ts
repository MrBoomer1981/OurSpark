/**
 * Вход вне Telegram: токен сессии PWA и (с DEBUG) подставной пользователь.
 * Живут в localStorage; в приватном режиме браузера не сохраняются — тогда вход нужен каждый раз.
 */
const TOKEN = 'gnezdo.session';
const DEBUG_USER = 'gnezdo.debugUser';

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
  clear: () => {
    write(TOKEN, null);
    write(DEBUG_USER, null);
  },
};
