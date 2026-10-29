import { useEffect } from 'react';

type Props = { text: string; onClose: () => void };

const SHOW_MS = 5000;

/** Строка внизу экрана о том, что случилось само: гнездо обновилось, пропала связь. Закрывается касанием. */
export function Toast({ text, onClose }: Props) {
  useEffect(() => {
    const timer = setTimeout(onClose, SHOW_MS);
    return () => clearTimeout(timer);
  }, [text, onClose]);

  return (
    <p className="toast" role="status" onClick={onClose}>
      {text}
    </p>
  );
}
