import { useState } from 'react';

type Props = {
  label: string;
  question: string;
  yes: string;
  no: string;
  busy: boolean;
  onConfirm: () => void;
};

/** Необратимое действие: сначала ссылка, по нажатию — вопрос и две кнопки. */
export function Confirm({ label, question, yes, no, busy, onConfirm }: Props) {
  const [asking, setAsking] = useState(false);
  if (!asking) {
    return (
      <button className="link" disabled={busy} onClick={() => setAsking(true)}>
        {label}
      </button>
    );
  }
  return (
    <div className="confirm">
      <p>{question}</p>
      <div className="row">
        <button
          className="button danger"
          disabled={busy}
          onClick={() => {
            setAsking(false);
            onConfirm();
          }}
        >
          {yes}
        </button>
        <button className="button secondary" onClick={() => setAsking(false)}>
          {no}
        </button>
      </div>
    </div>
  );
}
