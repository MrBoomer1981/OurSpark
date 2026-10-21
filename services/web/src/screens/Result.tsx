import type { Me } from '../api/client';
import { PetView } from '../pet/PetView';
import { texts } from '../texts';
import { BackLink } from '../ui/BackLink';

type Props = { me: Me; onBack: () => void };

/** Результат: оба выбора, общая реакция питомца, что получила пара. */
export function Result({ me, onBack }: Props) {
  const prompt = me.prompt;
  const result = prompt?.result;
  if (!prompt || !result || !prompt.mine) return null;
  const partnerName = me.pair?.partner?.name ?? '';
  const rewards = [texts.result.sparks(result.sparks), ...result.traits.map((t) => texts.result.shift(t.name, t.delta))];

  return (
    <main className="screen">
      <BackLink onBack={onBack} />
      <section className="nest">
        <PetView sprite="pet.hatchling" />
        <p className="bubble">{result.line}</p>
      </section>
      <section className="card">
        <p className="muted small">{prompt.card.text}</p>
        <p>
          {texts.result.you}: <b>{prompt.mine.text}</b>
        </p>
        <p>
          <b>{partnerName}</b>: {result.partner.text}
        </p>
        <p className="reward">{rewards.join(' · ')}</p>
      </section>
      <button className="button" onClick={onBack}>
        {texts.result.toNest}
      </button>
      <p className="muted small center-text">{texts.prompt.tomorrow}</p>
    </main>
  );
}
