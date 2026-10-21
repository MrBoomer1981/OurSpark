import { useState } from 'react';

import { api, call, type Me, type Result } from '../api/client';
import { launch } from '../platform';
import { credentials } from '../platform/credentials';
import { errorText, texts } from '../texts';

const DEBUG_USERS = [-1, -2];

type Props = {
  me: Me | null;
  onMe: (me: Me) => void;
  onUnauthorized: () => void;
  onSwitch: () => void;
};

/** Отладочная панель. Видна, только когда api запущен с DEBUG=true; без него api отклоняет эти запросы. */
export function DebugPanel({ me, onMe, onUnauthorized, onSwitch }: Props) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  // В браузере вне Telegram вход — подставным пользователем; между ними можно переключаться.
  const browserUser = launch.mode === 'pwa' ? credentials.debugUser() : null;
  const prompt = me?.prompt;
  const partnerCanAnswer =
    prompt !== null && prompt !== undefined && (prompt.state === 'WAITING_FOR_PARTNER' || (prompt.state === 'ASSIGNED' && !prompt.partner_answered));

  async function run(request: Promise<Result<Me>>) {
    setMessage(null);
    const result = await request;
    if (result.ok) onMe(result.data);
    else if (result.status === 401) onUnauthorized();
    else setMessage(errorText(result.code));
  }

  return (
    <aside className="debug">
      {open && (
        <div className="debug-panel">
          <p className="small">
            {texts.debug.title}: {me ? `${me.name} · ${me.id}` : '—'}
          </p>
          {prompt && <p className="small muted">{texts.debug.day(prompt.day)}</p>}
          {me?.pair?.status === 'waiting' && (
            <button className="button secondary" onClick={() => void run(call(api.POST('/api/debug/partner')))}>
              {texts.debug.partner}
            </button>
          )}
          {partnerCanAnswer && (
            <button className="button secondary" onClick={() => void run(call(api.POST('/api/debug/partner-answer')))}>
              {texts.debug.partnerAnswer}
            </button>
          )}
          {me?.pair?.status === 'complete' && (
            <button className="button secondary" onClick={() => void run(call(api.POST('/api/debug/next-day')))}>
              {texts.debug.nextDay}
            </button>
          )}
          {browserUser !== null &&
            DEBUG_USERS.filter((id) => id !== browserUser).map((id) => (
              <button
                key={id}
                className="button secondary"
                onClick={() => {
                  credentials.setDebugUser(id);
                  onSwitch();
                }}
              >
                {texts.debug.playAs} «{texts.debug.stubUser(-id)}»
              </button>
            ))}
          {browserUser !== null && (
            <button
              className="button secondary"
              onClick={() => {
                credentials.clear();
                onSwitch();
              }}
            >
              {texts.debug.logout}
            </button>
          )}
          {message && <p className="small">{message}</p>}
        </div>
      )}
      <button className="debug-toggle" aria-label={texts.debug.title} onClick={() => setOpen(!open)}>
        🐞
      </button>
    </aside>
  );
}
