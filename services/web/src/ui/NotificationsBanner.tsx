import { useState } from 'react';

import { api, call, type AppConfig, type Me } from '../api/client';
import { launch } from '../platform';
import { enablePush, pushSupported } from '../platform/push';
import { askWriteAccess } from '../platform/telegram';
import { errorText, texts } from '../texts';

type Props = { me: Me; config: AppConfig; onMe: (me: Me) => void };

/**
 * Плашка «уведомления выключены», когда не работает ни один канал.
 * В Telegram — разрешение боту писать (requestWriteAccess), в PWA — подписка на web push.
 */
export function NotificationsBanner({ me, config, onMe }: Props) {
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { telegram, push } = me.notifications;
  if (push || telegram === 'on') return null;

  const inTelegram = launch.mode === 'telegram';
  const publicKey = config.vapid_public_key;
  const canPush = !inTelegram && publicKey !== null && pushSupported();

  async function allowBot() {
    setBusy(true);
    if (await askWriteAccess()) {
      const result = await call(api.POST('/api/notifications/telegram'));
      if (result.ok) onMe(result.data);
      else setNote(errorText(result.code));
    }
    setBusy(false);
  }

  async function turnOnPush(key: string) {
    setBusy(true);
    const result = await enablePush(key);
    setBusy(false);
    if (result === 'denied') setNote(texts.notifications.denied);
    else if (result === 'unsupported') setNote(texts.notifications.installFirst);
    else if (result.ok) onMe(result.data);
    else setNote(errorText(result.code));
  }

  // Вне Telegram без поддержки push (например, Safari до установки на экран) — только подсказка.
  const hint = !inTelegram && !canPush ? texts.notifications.installFirst : null;

  return (
    <section className="card warning">
      <p className="small">{texts.notifications.off}</p>
      {inTelegram && (
        <button className="button secondary" disabled={busy} onClick={() => void allowBot()}>
          {texts.notifications.allowBot}
        </button>
      )}
      {canPush && publicKey && (
        <button className="button secondary" disabled={busy} onClick={() => void turnOnPush(publicKey)}>
          {texts.notifications.enablePush}
        </button>
      )}
      {(note ?? hint) && <p className="muted small">{note ?? hint}</p>}
    </section>
  );
}
