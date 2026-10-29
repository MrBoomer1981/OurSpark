import { texts } from '../texts';
import { Icon } from '../ui/Icon';

type Props = {
  text: string;
  action?: { label: string; onClick: () => void };
};

/** Экран с одной фразой: загрузка, нет связи, пора открыть гнездо заново. */
export function Notice({ text, action }: Props) {
  return (
    <main className="screen center">
      <Icon name="habit" scale={5} />
      <h1 className="title">{texts.appName}</h1>
      <p className="muted">{text}</p>
      {action && (
        <button className="button" onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </main>
  );
}
