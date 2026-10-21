import { useState } from 'react';

import { api, call, type Me } from '../api/client';
import { PetView, type Pet } from '../pet/PetView';
import { errorText, texts } from '../texts';
import { BackLink } from '../ui/BackLink';

type Prompt = NonNullable<Me['prompt']>;

type Props = {
  prompt: Prompt;
  pet: Pet | null;
  onMe: (me: Me) => void;
  onUnauthorized: () => void;
  onReveal: () => void;
  onBack: () => void;
};

/** Послание: карточка, варианты, что увидит партнёр, «Отправить». После ответа — реакция питомца. */
export function Message({ prompt, pet, onMe, onUnauthorized, onReveal, onBack }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function send() {
    if (selected === null) return;
    setBusy(true);
    setMessage(null);
    const result = await call(api.POST('/api/prompt/answer', { body: { session_id: prompt.session_id, option: selected } }));
    setBusy(false);
    if (result.ok) onMe(result.data);
    else if (result.status === 401) onUnauthorized();
    else setMessage(errorText(result.code));
  }

  if (prompt.mine) {
    // Ответ уже есть: реакция питомца и награда за участие.
    return (
      <main className="screen">
        <BackLink onBack={onBack} />
        <section className="nest">
          {pet && <PetView pet={pet} />}
          {prompt.reaction && <p className="bubble">{prompt.reaction}</p>}
          {prompt.answer_sparks !== null && <p className="reward">{texts.message.reward(prompt.answer_sparks)}</p>}
        </section>
        {prompt.state === 'READY_TO_REVEAL' ? (
          <button className="button" onClick={onReveal}>
            {texts.message.revealNow}
          </button>
        ) : (
          <button className="button" onClick={onBack}>
            {texts.message.toNest}
          </button>
        )}
      </main>
    );
  }

  return (
    <main className="screen">
      <BackLink onBack={onBack} />
      <section className="card">
        <p className="muted small">{texts.message.kind[prompt.card.kind] ?? texts.prompt.title}</p>
        <h2>{prompt.card.text}</h2>
        <div className="options">
          {prompt.card.options.map((option) => (
            <button
              key={option.key}
              className={option.key === selected ? 'option selected' : 'option'}
              aria-pressed={option.key === selected}
              onClick={() => setSelected(option.key)}
            >
              {option.text}
            </button>
          ))}
        </div>
        <p className="muted small">{texts.message.privacy}</p>
        <button className="button" disabled={selected === null || busy} onClick={() => void send()}>
          {texts.message.send}
        </button>
        {message && <p className="message">{message}</p>}
      </section>
    </main>
  );
}
