import { useState } from 'react';

import { api, call, type AppConfig, type Me, type Result } from '../api/client';
import { Growth } from '../pet/Growth';
import { PetView } from '../pet/PetView';
import { copyText, shareLink } from '../platform/share';
import { errorText, texts } from '../texts';
import { Confirm } from '../ui/Confirm';
import { InstallOffer } from '../ui/InstallOffer';
import { NotificationsBanner } from '../ui/NotificationsBanner';

/** Приглашение, по которому Mini App открыли, не сработало: код и причина от api. */
export type InviteProblem = { code: string; problem: string };

type Pair = NonNullable<Me['pair']>;
type Prompt = NonNullable<Me['prompt']>;

type Props = {
  me: Me;
  config: AppConfig;
  invite: InviteProblem | null;
  onMe: (me: Me) => void;
  onInvite: (invite: InviteProblem | null) => void;
  onUnauthorized: () => void;
  onOpenMessage: () => void;
  onReveal: () => void;
  onShowResult: () => void;
  onOpenPet: () => void;
  onOpenChronicle: () => void;
};

/** Гнездо: нет пары → ждём партнёра → пара в сборе: питомец, послание дня, входы в «Питомца» и «Летопись». */
export function Nest(props: Props) {
  const { me, config, invite, onMe, onInvite, onUnauthorized } = props;
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
        <>
          <Together me={me} pair={me.pair} />
          {me.prompt && <PromptStatus prompt={me.prompt} {...props} />}
          <div className="row">
            <button className="button secondary" onClick={props.onOpenPet}>
              {texts.complete.pet}
            </button>
            <button className="button secondary" onClick={props.onOpenChronicle}>
              {texts.complete.chronicle}
            </button>
          </div>
          <NotificationsBanner me={me} config={config} onMe={onMe} />
          <Confirm
            label={texts.complete.leave}
            question={texts.complete.leaveConfirm}
            yes={texts.complete.leaveYes}
            no={texts.complete.leaveNo}
            busy={busy}
            onConfirm={() => void leave()}
          />
        </>
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

function Together({ me, pair }: { me: Me; pair: Pair }) {
  return (
    <section className="nest">
      {me.pet && <PetView pet={me.pet} />}
      {me.pet_line && <p className="bubble">{me.pet_line}</p>}
      <p className="small">
        {texts.complete.together} <b>{pair.partner?.name}</b>
      </p>
      {me.pet && (
        <>
          <Growth pet={me.pet} />
          <p className="muted small">{texts.complete.sparks(me.pet.sparks)}</p>
        </>
      )}
    </section>
  );
}

type PromptStatusProps = { prompt: Prompt; onOpenMessage: () => void; onReveal: () => void; onShowResult: () => void };

function PromptStatus({ prompt, onOpenMessage, onReveal, onShowResult }: PromptStatusProps) {
  if (prompt.state === 'ASSIGNED') {
    return (
      <section className="card">
        <h2>{texts.prompt.title}</h2>
        <p className="muted small">{texts.message.kind[prompt.card.kind]}</p>
        {prompt.partner_answered && <p className="muted">{texts.prompt.partnerAnswered}</p>}
        <button className="button" onClick={onOpenMessage}>
          {texts.prompt.answer}
        </button>
      </section>
    );
  }
  if (prompt.state === 'WAITING_FOR_PARTNER') {
    return (
      <section className="card">
        <h2>{texts.prompt.waitingTitle}</h2>
        <p className="muted">
          {texts.prompt.yourAnswer}: <b>{short(prompt.mine?.text ?? '')}</b>
        </p>
      </section>
    );
  }
  if (prompt.state === 'READY_TO_REVEAL' || !prompt.seen) {
    return (
      <section className="card">
        <h2>{texts.prompt.readyTitle}</h2>
        <button className="button" onClick={onReveal}>
          {texts.prompt.reveal}
        </button>
      </section>
    );
  }
  return (
    <section className="card">
      <h2>{texts.prompt.doneTitle}</h2>
      <p className="muted">{texts.prompt.tomorrow}</p>
      <button className="link" onClick={onShowResult}>
        {texts.prompt.showResult}
      </button>
    </section>
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

/** Длинный ответ текстом в Гнезде — только начало. */
function short(text: string, limit = 80): string {
  return text.length > limit ? `${text.slice(0, limit).trimEnd()}…` : text;
}
