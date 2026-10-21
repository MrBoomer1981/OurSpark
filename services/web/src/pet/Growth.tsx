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
          <progress max={next.sparks} value={Math.min(pet.earned, next.sparks)} />
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
