import { useCallback, useEffect, useState } from 'react';

import { api, call, hasCredentials, type AppConfig, type Me } from './api/client';
import { DebugPanel } from './debug/DebugPanel';
import { launch } from './platform';
import { credentials } from './platform/credentials';
import { Login } from './screens/Login';
import { Nest, type InviteProblem } from './screens/Nest';
import { Notice } from './screens/Notice';
import { texts } from './texts';

type View =
  | { kind: 'loading' }
  | { kind: 'offline' }
  | { kind: 'reopen' } // Telegram: initData устарела, Mini App пора открыть заново
  | { kind: 'login' } // PWA без сессии
  | { kind: 'nest'; me: Me };

export function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [view, setView] = useState<View>({ kind: 'loading' });
  const [invite, setInvite] = useState<InviteProblem | null>(null);

  const unauthorized = useCallback(() => {
    if (launch.mode === 'telegram') {
      setView({ kind: 'reopen' });
    } else {
      credentials.clear();
      setView({ kind: 'login' });
    }
  }, []);

  const refresh = useCallback(async () => {
    if (!hasCredentials()) {
      setView({ kind: 'login' });
      return;
    }
    const result = await call(api.GET('/api/me'));
    if (result.ok) setView({ kind: 'nest', me: result.data });
    else if (result.status === 401) unauthorized();
    else setView({ kind: 'offline' });
  }, [unauthorized]);

  const boot = useCallback(async () => {
    setView({ kind: 'loading' });
    const settings = await call(api.GET('/api/config'));
    if (!settings.ok) {
      setView({ kind: 'offline' });
      return;
    }
    setConfig(settings.data);
    // Mini App открыли по приглашению — входим в пару сразу. Повторный вход в свою пару не ошибка.
    const code = launch.startParam;
    if (code && hasCredentials()) {
      const joined = await call(api.POST('/api/pairs/join', { body: { code } }));
      if (joined.ok) {
        setView({ kind: 'nest', me: joined.data });
        return;
      }
      if (joined.status === 409) setInvite({ code, problem: joined.code });
    }
    await refresh();
  }, [refresh]);

  useEffect(() => {
    void boot();
  }, [boot]);

  // Вернулись в приложение (например, из уведомления) — подтягиваем свежее состояние.
  useEffect(() => {
    if (config === null) return;
    const onVisible = () => {
      if (document.visibilityState === 'visible') void refresh();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [config, refresh]);

  const showMe = useCallback((me: Me) => setView({ kind: 'nest', me }), []);

  return (
    <>
      {view.kind === 'loading' && <Notice text={texts.loading} />}
      {view.kind === 'offline' && <Notice text={texts.offline} action={{ label: texts.retry, onClick: () => void boot() }} />}
      {view.kind === 'reopen' && <Notice text={texts.reopen} />}
      {view.kind === 'login' && config && <Login config={config} onLoggedIn={() => void boot()} />}
      {view.kind === 'nest' && config && (
        <Nest
          me={view.me}
          config={config}
          invite={invite}
          onMe={showMe}
          onInvite={setInvite}
          onUnauthorized={unauthorized}
        />
      )}
      {config?.debug && (
        <DebugPanel
          me={view.kind === 'nest' ? view.me : null}
          onMe={showMe}
          onUnauthorized={unauthorized}
          onSwitch={() => void boot()}
        />
      )}
    </>
  );
}
