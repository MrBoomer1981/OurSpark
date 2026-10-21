import { launch } from '../platform';
import { useBackButton } from '../platform/telegram';
import { texts } from '../texts';

/** «Назад» со вторичного экрана: в Telegram — его кнопка в шапке, вне Telegram — ссылка над экраном. */
export function BackLink({ onBack }: { onBack: () => void }) {
  useBackButton(onBack);
  if (launch.mode === 'telegram') return null;
  return (
    <button className="link back" onClick={onBack}>
      {texts.back}
    </button>
  );
}
