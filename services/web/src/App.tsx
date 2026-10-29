import { useCallback, useEffect, useRef, useState } from 'react';

import { api, call, hasCredentials, type AppConfig, type Me } from './api/client';
import { isStale } from './api/useAction';
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
import { errorText, texts } from './texts';
import { Toast } from './ui/Toast';

type View =
  | { kind: 'loading' }
  | { kind: 'offline' }
  | { kind: 'reopen' } // Telegram: initData устарела, Mini App пора открыть заново
  | { kind: 'login'; ended: boolean } // PWA без сессии; ended — сессия была, но больше не действует
  | { kind: 'nest'; me: Me };

// Главный путь ведёт к посланию; остальное — вторичные экраны с кнопкой «назад».
type Screen = 'nest' | 'message' | 'result' | 'pet' | 'chronicle';

export function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [view, setView] = useState<View>({ kind: 'loading' });
  const [screen, setScreen] = useState<Screen>('nest');
  const [invite, setInvite] = useState<InviteProblem | null>(null);
  const [flash, setFlash] = useState<string | null>(null); // строка внизу экрана о том, что случилось само
  const shown = useRef(false); // гнездо уже на экране: при сбое обновления оставляем его, а не прячем
  useEffect(() => {
    shown.current = view.kind === 'nest';
  }, [view.kind]);

  const unauthorized = useCallback(() => {
    if (launch.mode === 'telegram') {
      setView({ kind: 'reopen' });
    } else {
      // Сессия была, но api её не принял. Запросов может быть несколько сразу: объяснение не теряется,
      // даже если следующий 401 придёт, когда токен уже стёрт.
      const ended = credentials.token() !== null;
      credentials.clear();
      setView((current) => ({ kind: 'login', ended: ended || (current.kind === 'login' && current.ended) }));
    }
  }, []);

  const refresh = useCallback(async () => {
    if (!hasCredentials()) {
      // Вход уже на экране (возможно, с объяснением, что прежний закончился) — его не перерисовываем.
      setView((current) => (current.kind === 'login' ? current : { kind: 'login', ended: false }));
      return;
    }
    const result = await call(api.GET('/api/me'));
    if (result.ok) setView({ kind: 'nest', me: result.data });
    else if (result.status === 401) unauthorized();
    else if (shown.current) setFlash(errorText(result.code));
    else setView({ kind: 'offline' });
  }, [unauthorized]);

  /** Экран устарел (послание сменилось, на него уже ответили…): гнездо заново и строка о том, что случилось. */
  const stale = useCallback(
    (code: string) => {
      setFlash(errorText(code));
      setScreen('nest');
      void refresh();
    },
    [refresh],
  );

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
  const closeFlash = useCallback(() => setFlash(null), []);

  const me = view.kind === 'nest' ? view.me : null;
  const sessionId = me?.prompt?.session_id;

  /** «Открыть результат»: раскрытие на сервере, потом экран результата. Сбой — объяснение, а не тихий возврат. */
  const reveal = useCallback(async () => {
    if (sessionId === undefined) return;
    const result = await call(api.POST('/api/prompt/reveal', { body: { session_id: sessionId } }));
    if (result.ok) {
      showMe(result.data);
      setScreen('result');
    } else if (result.status === 401) {
      unauthorized();
    } else if (isStale(result.code)) {
      stale(result.code);
    } else {
      setFlash(errorText(result.code)); // нет связи или сбой api: остаёмся, можно нажать ещё раз
    }
  }, [sessionId, showMe, unauthorized, stale]);

  let content = null;
  if (view.kind === 'loading') content = <Notice text={texts.loading} busy />;
  else if (view.kind === 'offline') content = <Notice text={texts.offline} action={{ label: texts.retry, onClick: () => void boot() }} />;
  else if (view.kind === 'reopen') content = <Notice text={texts.reopen} />;
  else if (view.kind === 'login' && config) content = <Login config={config} ended={view.ended} onLoggedIn={() => void boot()} />;
  else if (view.kind === 'nest' && config) {
    const prompt = view.me.prompt;
    const handlers = { onMe: showMe, onUnauthorized: unauthorized, onStale: stale };
    if (screen === 'message' && prompt) {
      content = (
        <Message
          key={prompt.session_id}
          prompt={prompt}
          pet={view.me.pet}
          {...handlers}
          onReveal={() => void reveal()}
          onBack={toNest}
        />
      );
    } else if (screen === 'result' && prompt?.result) {
      content = <Result me={view.me} onBack={toNest} />;
    } else if (screen === 'pet' && view.me.pet) {
      content = <Pet me={view.me} {...handlers} onBack={toNest} />;
    } else if (screen === 'chronicle' && view.me.pet) {
      content = <Chronicle me={view.me} onUnauthorized={unauthorized} onBack={toNest} />;
    } else {
      content = (
        <Nest
          me={view.me}
          config={config}
          invite={invite}
          {...handlers}
          onInvite={setInvite}
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
      {flash && <Toast text={flash} onClose={closeFlash} />}
      {config?.debug && <DebugPanel me={me} onMe={showMe} onUnauthorized={unauthorized} onSwitch={() => void boot()} />}
    </>
  );
}
