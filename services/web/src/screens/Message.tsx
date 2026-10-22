import { useState } from 'react';

import { api, call, type Me, type Result } from '../api/client';
import { PetView, type Pet } from '../pet/PetView';
import { errorText, texts } from '../texts';
import { BackLink } from '../ui/BackLink';

type Prompt = NonNullable<Me['prompt']>;
type Card = Prompt['card'];

type Props = {
  prompt: Prompt;
  pet: Pet | null;
  onMe: (me: Me) => void;
  onUnauthorized: () => void;
  onReveal: () => void;
  onBack: () => void;
};

/**
 * Послание: карточка и ответ по её типу — вариант, текст или вариант с прогнозом; что увидит партнёр;
 * «Отправить» и «Другой вопрос». После ответа — реакция питомца.
 */
export function Message({ prompt, pet, onMe, onUnauthorized, onReveal, onBack }: Props) {
  const [option, setOption] = useState<string | null>(null);
  const [prediction, setPrediction] = useState<string | null>(null);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const card = prompt.card;

  async function run(request: Promise<Result<Me>>) {
    setBusy(true);
    setMessage(null);
    const result = await request;
    setBusy(false);
    if (result.ok) onMe(result.data);
    else if (result.status === 401) onUnauthorized();
    else setMessage(errorText(result.code));
  }

  const ready =
    card.kind === 'closeness'
      ? text.trim().length > 0
      : option !== null && (card.kind !== 'guess' || prediction !== null);

  function send() {
    const body =
      card.kind === 'closeness'
        ? { session_id: prompt.session_id, text }
        : { session_id: prompt.session_id, option, prediction: card.kind === 'guess' ? prediction : null };
    void run(call(api.POST('/api/prompt/answer', { body })));
  }

  function change() {
    void run(call(api.POST('/api/prompt/change', { body: { session_id: prompt.session_id } })));
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
        <section className="card">
          <p className="muted small">{card.text}</p>
          <p>
            <b>{texts.message.mine}:</b> {prompt.mine.text}
          </p>
          {prompt.prediction && (
            <p>
              <b>{texts.message.prediction}:</b> {prompt.prediction.text}
            </p>
          )}
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
        <p className="muted small">{texts.message.kind[card.kind] ?? texts.prompt.title}</p>
        <h2>{card.text}</h2>
        {card.kind === 'closeness' ? (
          <TextAnswer value={text} max={card.max_length} onChange={setText} />
        ) : card.kind === 'guess' ? (
          <>
            <h3>{texts.message.yourAnswer}</h3>
            <Options card={card} selected={option} onSelect={setOption} />
            <h3>{texts.message.yourGuess}</h3>
            <Options card={card} selected={prediction} onSelect={setPrediction} />
          </>
        ) : (
          <Options card={card} selected={option} onSelect={setOption} />
        )}
        <p className="muted small">{texts.message.privacy[card.kind]}</p>
        <button className="button" disabled={!ready || busy} onClick={send}>
          {texts.message.send}
        </button>
        {prompt.changes_left > 0 && (
          <button className="link" disabled={busy} onClick={change}>
            {texts.message.change(prompt.changes_left)}
          </button>
        )}
        {message && <p className="message">{message}</p>}
      </section>
    </main>
  );
}

type OptionsProps = { card: Card; selected: string | null; onSelect: (key: string) => void };

function Options({ card, selected, onSelect }: OptionsProps) {
  return (
    <div className="options">
      {card.options.map((option) => (
        <button
          key={option.key}
          className={option.key === selected ? 'option selected' : 'option'}
          aria-pressed={option.key === selected}
          onClick={() => onSelect(option.key)}
        >
          {option.text}
        </button>
      ))}
    </div>
  );
}

type TextAnswerProps = { value: string; max: number | null; onChange: (value: string) => void };

/** Ответ о близости — свободный текст. */
function TextAnswer({ value, max, onChange }: TextAnswerProps) {
  return (
    <div className="stack">
      <textarea
        className="textarea"
        value={value}
        maxLength={max ?? undefined}
        placeholder={texts.message.placeholder}
        rows={5}
        onChange={(event) => onChange(event.target.value)}
      />
      {max !== null && <p className="muted small counter">{texts.message.counter(value.length, max)}</p>}
    </div>
  );
}
