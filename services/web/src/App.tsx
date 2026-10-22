import { useCallback, useEffect, useState } from 'react';

import { api, call, hasCredentials, type AppConfig, type Me } from './api/client';
import { DebugPanel } from './debug/DebugPanel';
import { launch } from './platform';
import { credentials } from './platform/credentials';
import { Chronicle } from './screens/Chronicle';
import { Login } from './screens/Login';
import { Message } from './screens/Message';
import { Nest, type InviteProblem } from './screens/Nest';
import { Notice } from './screens/Notice';
import { Pet } from './screens/Pet';
import { Result } from './screens/Result';
import { texts } from './texts';

type View =
  | { kind: 'loading' }
  | { kind: 'offline' }
  | { kind: 'reopen' } // Telegram: initData устарела, Mini App пора открыть заново
  | { kind: 'login' } // PWA без сессии
  | { kind: 'nest'; me: Me };

// Главный путь ведёт к посланию; остальное — вторичные экраны с кнопкой «назад».
type Screen = 'nest' | 'message' | 'result' | 'pet' | 'chronicle';

export function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [view, setView] = useState<View>({ kind: 'loading' });
  const [screen, setScreen] = useState<Screen>('nest');
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
    setScreen('nest');
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
  const toNest = useCallback(() => setScreen('nest'), []);

  const me = view.kind === 'nest' ? view.me : null;
  const sessionId = me?.prompt?.session_id;

  /** «Открыть результат»: раскрытие на сервере, потом экран результата. */
  const reveal = useCallback(async () => {
    if (sessionId === undefined) return;
    const result = await call(api.POST('/api/prompt/reveal', { body: { session_id: sessionId } }));
    if (result.ok) {
      showMe(result.data);
      setScreen('result');
    } else if (result.status === 401) {
      unauthorized();
    } else {
      setScreen('nest');
      await refresh();
    }
  }, [sessionId, showMe, unauthorized, refresh]);

  let content = null;
  if (view.kind === 'loading') content = <Notice text={texts.loading} />;
  else if (view.kind === 'offline') content = <Notice text={texts.offline} action={{ label: texts.retry, onClick: () => void boot() }} />;
  else if (view.kind === 'reopen') content = <Notice text={texts.reopen} />;
  else if (view.kind === 'login' && config) content = <Login config={config} onLoggedIn={() => void boot()} />;
  else if (view.kind === 'nest' && config) {
    const prompt = view.me.prompt;
    if (screen === 'message' && prompt) {
      content = (
        <Message
          key={prompt.session_id}
          prompt={prompt}
          pet={view.me.pet}
          onMe={showMe}
          onUnauthorized={unauthorized}
          onReveal={() => void reveal()}
          onBack={toNest}
        />
      );
    } else if (screen === 'result' && prompt?.result) {
      content = <Result me={view.me} onBack={toNest} />;
    } else if (screen === 'pet' && view.me.pet) {
      content = <Pet me={view.me} onMe={showMe} onUnauthorized={unauthorized} onBack={toNest} />;
    } else if (screen === 'chronicle' && view.me.pet) {
      content = <Chronicle me={view.me} onUnauthorized={unauthorized} onBack={toNest} />;
    } else {
      content = (
        <Nest
          me={view.me}
          config={config}
          invite={invite}
          onMe={showMe}
          onInvite={setInvite}
          onUnauthorized={unauthorized}
          onOpenMessage={() => setScreen('message')}
          onReveal={() => void reveal()}
          onShowResult={() => setScreen('result')}
          onOpenPet={() => setScreen('pet')}
          onOpenChronicle={() => setScreen('chronicle')}
        />
      );
    }
  }

  return (
    <>
      {content}
      {config?.debug && <DebugPanel me={me} onMe={showMe} onUnauthorized={unauthorized} onSwitch={() => void boot()} />}
    </>
  );
}
