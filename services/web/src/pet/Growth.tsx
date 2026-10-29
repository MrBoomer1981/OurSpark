import { texts } from '../texts';
import type { Pet } from './PetView';

/** Стадия и полоска до следующей. Прогресс — все заработанные искры, траты не в счёт. */
export function Growth({ pet }: { pet: Pet }) {
  const current = pet.stages.find((stage) => stage.key === pet.stage);
  const next = pet.stages.find((stage) => !stage.reached);
  return (
    <div className="growth">
      <p>
        <b>{current?.name}</b>
      </p>
      {next ? (
        <>
          <Bar value={pet.earned} max={next.sparks} label={texts.pet.toNext(next.name, pet.earned, next.sparks)} />
          <p className="muted small">
            {pet.earned >= next.sparks
              ? texts.pet.growsSoon(next.name)
              : texts.pet.toNext(next.name, pet.earned, next.sparks)}
          </p>
        </>
      ) : (
        <p className="muted small">{texts.pet.lastStage}</p>
      )}
    </div>
  );
}

type BarProps = { value: number; max: number; label: string; kind?: 'trait' };

/** Пиксельная полоска прогресса. */
export function Bar({ value, max, label, kind }: BarProps) {
  const share = max > 0 ? Math.min(value / max, 1) : 1;
  return (
    <div
      className={kind ? `bar ${kind}` : 'bar'}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={Math.min(value, max)}
    >
      <span style={{ width: `${share * 100}%` }} />
    </div>
  );
}
