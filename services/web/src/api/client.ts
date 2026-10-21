import createClient from 'openapi-fetch';

import { launch } from '../platform';
import { credentials } from '../platform/credentials';
import type { components, paths } from './schema';

export type Me = components['schemas']['Me'];
export type AppConfig = components['schemas']['AppConfig'];

/** Клиент api. Пути и типы — из схемы OpenAPI: после правок api — npm run api:types. */
export const api = createClient<paths>();

api.use({
  onRequest({ request }) {
    const header = authorization();
    if (header) request.headers.set('Authorization', header);
    return request;
  },
});

/** Кто я для api: подпись Telegram, токен сессии PWA или (с DEBUG) подставной пользователь. */
function authorization(): string | undefined {
  if (launch.mode === 'telegram') return launch.initData ? `tma ${launch.initData}` : undefined;
  const token = credentials.token();
  if (token) return `Bearer ${token}`;
  const debugUser = credentials.debugUser();
  return debugUser !== null ? `debug ${debugUser}` : undefined;
}

export function hasCredentials(): boolean {
  return authorization() !== undefined;
}

/** Ответ api одним видом: данные или код ошибки (detail из ответа, network — нет связи). */
export type Result<T> = { ok: true; data: T } | { ok: false; status: number; code: string };

export async function call<T>(request: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<Result<T>> {
  try {
    const { data, error, response } = await request;
    if (data !== undefined) return { ok: true, data };
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    return { ok: false, status: response.status, code: typeof detail === 'string' ? detail : 'unknown' };
  } catch {
    return { ok: false, status: 0, code: 'network' };
  }
}
