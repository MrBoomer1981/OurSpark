import { useState } from 'react';

import { api, call, type AppConfig, type Me, type Result } from '../api/client';
import { PetView } from '../pet/PetView';
import { copyText, shareLink } from '../platform/share';
import { errorText, texts } from '../texts';
import { Confirm } from '../ui/Confirm';
import { InstallOffer } from '../ui/InstallOffer';

/** Приглашение, по которому Mini App открыли, не сработало: код и причина от api. */
export type InviteProblem = { code: string; problem: string };

type Pair = NonNullable<Me['pair']>;

type Props = {
  me: Me;
  config: AppConfig;
  invite: InviteProblem | null;
  onMe: (me: Me) => void;
  onInvite: (invite: InviteProblem | null) => void;
  onUnauthorized: () => void;
};

/** Гнездо: нет пары → ждём партнёра → пара в сборе и питомец. */
export function Nest({ me, config, invite, onMe, onInvite, onUnauthorized }: Props) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  /** Действие с ответом-состоянием: при успехе показывает новое состояние, при ошибке — понятный текст. */
  async function run(request: Promise<Result<Me>>): Promise<boolean> {
    setBusy(true);
    setMessage(null);
    const result = await request;
    setBusy(false);
    if (result.ok) {
      onMe(result.data);
      return true;
    }
    if (result.status === 401) onUnauthorized();
    else setMessage(errorText(result.code));
    return false;
  }

  const create = () => run(call(api.POST('/api/pairs')));
  const leave = () => run(call(api.POST('/api/pairs/leave')));

  async function leaveAndJoin(code: string) {
    if (!(await leave())) return;
    const result = await call(api.POST('/api/pairs/join', { body: { code } }));
    if (result.ok) {
      onMe(result.data);
      onInvite(null);
    } else if (result.status === 409) {
      onInvite({ code, problem: result.code });
    } else if (result.status === 401) {
      onUnauthorized();
    } else {
      setMessage(errorText(result.code));
    }
  }

  return (
    <main className="screen">
      <h1 className="title">{texts.appName}</h1>
      {invite && (
        <InviteCard
          invite={invite}
          busy={busy}
          onLeaveAndJoin={() => void leaveAndJoin(invite.code)}
          onDismiss={() => onInvite(null)}
        />
      )}
      {me.pair === null ? (
        <NoPair busy={busy} newPairs={config.new_pairs} onCreate={() => void create()} />
      ) : me.pair.status === 'waiting' ? (
        <Waiting pair={me.pair} busy={busy} onCancel={() => void leave()} />
      ) : (
        <Together pair={me.pair} busy={busy} onLeave={() => void leave()} />
      )}
      {message && <p className="message">{message}</p>}
      <InstallOffer />
    </main>
  );
}

function NoPair({ busy, newPairs, onCreate }: { busy: boolean; newPairs: boolean; onCreate: () => void }) {
  return (
    <section className="card">
      <p>{texts.noPair.lead}</p>
      {newPairs ? (
        <>
          <p className="muted">{texts.noPair.hint}</p>
          <button className="button" disabled={busy} onClick={onCreate}>
            {texts.noPair.create}
          </button>
        </>
      ) : (
        <p className="muted">{texts.errors.new_pairs_closed}</p>
      )}
    </section>
  );
}

function Waiting({ pair, busy, onCancel }: { pair: Pair; busy: boolean; onCancel: () => void }) {
  const [note, setNote] = useState<string | null>(null);
  const link = pair.invite_link;

  async function share(how: 'share' | 'copy') {
    if (!link) return;
    const result = how === 'share' ? await shareLink(link, texts.waiting.shareText) : await copyText(link);
    if (result === 'copied') setNote(texts.waiting.copied);
  }

  return (
    <section className="card">
      <h2>{texts.waiting.title}</h2>
      <p className="muted">{texts.waiting.lead}</p>
      {link ? (
        <>
          <p className="invite">{link}</p>
          <button className="button" onClick={() => void share('share')}>
            {texts.waiting.share}
          </button>
          <button className="button secondary" onClick={() => void share('copy')}>
            {texts.waiting.copy}
          </button>
        </>
      ) : (
        <p className="invite">
          {texts.waiting.code}: {pair.invite_code}
        </p>
      )}
      {note && <p className="muted small">{note}</p>}
      <Confirm
        label={texts.waiting.cancel}
        question={texts.waiting.cancelConfirm}
        yes={texts.waiting.cancelYes}
        no={texts.waiting.cancelNo}
        busy={busy}
        onConfirm={onCancel}
      />
    </section>
  );
}

function Together({ pair, busy, onLeave }: { pair: Pair; busy: boolean; onLeave: () => void }) {
  return (
    <>
      <section className="nest">
        <PetView sprite="pet.hatchling" />
        <p>
          {texts.complete.together} <b>{pair.partner?.name}</b>
        </p>
        <p className="muted">{texts.complete.hatched}</p>
      </section>
      <Confirm
        label={texts.complete.leave}
        question={texts.complete.leaveConfirm}
        yes={texts.complete.leaveYes}
        no={texts.complete.leaveNo}
        busy={busy}
        onConfirm={onLeave}
      />
    </>
  );
}

type InviteCardProps = {
  invite: InviteProblem;
  busy: boolean;
  onLeaveAndJoin: () => void;
  onDismiss: () => void;
};

function InviteCard({ invite, busy, onLeaveAndJoin, onDismiss }: InviteCardProps) {
  return (
    <section className="card warning">
      <p>{texts.invite[invite.problem] ?? texts.invite.unknown}</p>
      {invite.problem === 'in_other_pair' && (
        <Confirm
          label={texts.invite.leaveAndJoin}
          question={texts.invite.leaveAndJoinConfirm}
          yes={texts.complete.leaveYes}
          no={texts.complete.leaveNo}
          busy={busy}
          onConfirm={onLeaveAndJoin}
        />
      )}
      <button className="button secondary" onClick={onDismiss}>
        {texts.invite.ok}
      </button>
    </section>
  );
}
