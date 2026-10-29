import { useCallback, useEffect, useState } from 'react';

import { api, call, type AppConfig } from '../api/client';
import { credentials } from '../platform/credentials';
import { texts } from '../texts';
import { Icon } from '../ui/Icon';

type LoginLink = { nonce: string; link: string };
type State = 'preparing' | 'ready' | 'waiting' | 'expired' | 'off' | 'error';

// nonce живёт 10 минут: обновляем его заранее, пока человек ещё не нажал «Войти».
const NONCE_REFRESH_MS = 9 * 60_000;
const POLL_MS = 2000;
const DEBUG_USERS = [-1, -2];

type Props = { config: AppConfig; onLoggedIn: () => void };

/** Вход в PWA через бота: ссылка t.me/<бот>?start=login_<nonce>, подтверждение в боте, токен сессии. */
export function Login({ config, onLoggedIn }: Props) {
  const [login, setLogin] = useState<LoginLink | null>(null);
  const [state, setState] = useState<State>('preparing');

  // nonce готовим заранее: тогда «Войти через Telegram» — обычная ссылка,
  // и iOS откроет Telegram с первого нажатия, без промежуточного запроса.
  const prepare = useCallback(async () => {
    setState('preparing');
    const result = await call(api.POST('/api/auth/login'));
    if (result.ok) {
      setLogin(result.data);
      setState('ready');
    } else {
      setState(result.status === 503 ? 'off' : 'error');
    }
  }, []);

  useEffect(() => {
    void prepare();
  }, [prepare]);

  useEffect(() => {
    if (state !== 'ready') return;
    const timer = setTimeout(() => void prepare(), NONCE_REFRESH_MS);
    return () => clearTimeout(timer);
  }, [state, prepare]);

  // После нажатия ждём подтверждения: опрос раз в пару секунд и сразу при возвращении в приложение.
  useEffect(() => {
    if (state !== 'waiting' || login === null) return;
    let active = true;
    const check = async () => {
      const result = await call(api.POST('/api/auth/login/exchange', { body: { nonce: login.nonce } }));
      if (!active) return;
      if (result.ok && result.data.token) {
        credentials.setToken(result.data.token);
        onLoggedIn();
      } else if (!result.ok && result.status === 410) {
        setState('expired');
      }
    };
    const timer = setInterval(() => void check(), POLL_MS);
    const onVisible = () => {
      if (document.visibilityState === 'visible') void check();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      active = false;
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [state, login, onLoggedIn]);

  return (
    <main className="screen center">
      <Icon name="seal" scale={5} />
      <h1 className="title">{texts.appName}</h1>
      <p className="muted">{texts.login.lead}</p>

      {(state === 'ready' || state === 'waiting') && login && (
        <a
          className="button"
          href={login.link}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => setState('waiting')}
        >
          {state === 'waiting' ? texts.login.again : texts.login.button}
        </a>
      )}
      {state === 'waiting' && <p className="muted small">{texts.login.waiting}</p>}
      {state === 'expired' && (
        <>
          <p className="muted">{texts.login.expired}</p>
          <button className="button" onClick={() => void prepare()}>
            {texts.login.restart}
          </button>
        </>
      )}
      {state === 'off' && <p className="muted">{texts.login.off}</p>}
      {state === 'error' && (
        <>
          <p className="muted">{texts.offline}</p>
          <button className="button" onClick={() => void prepare()}>
            {texts.retry}
          </button>
        </>
      )}

      {config.debug && (
        <section className="stack">
          <p className="muted small">{texts.login.debug}</p>
          {DEBUG_USERS.map((id) => (
            <button
              key={id}
              className="button secondary"
              onClick={() => {
                credentials.setDebugUser(id);
                onLoggedIn();
              }}
            >
              {texts.debug.stubUser(-id)}
            </button>
          ))}
        </section>
      )}
    </main>
  );
}
