import { useState } from 'react';

import { api, call, type Me, type Result } from '../api/client';
import { Growth } from '../pet/Growth';
import { PetView, type Pet as PetData } from '../pet/PetView';
import { errorText, texts } from '../texts';
import { BackLink } from '../ui/BackLink';

type Item = PetData['items'][number];

type Props = { me: Me; onMe: (me: Me) => void; onUnauthorized: () => void; onBack: () => void };

/** Питомец: стадии, характер и привычки, косметика с примеркой. */
export function Pet({ me, onMe, onUnauthorized, onBack }: Props) {
  const [open, setOpen] = useState<string | null>(null); // раскрытый предмет — его и примеряем
  const [reaction, setReaction] = useState<{ item: string; text: string } | null>(null); // питомец об обнове
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const pet = me.pet;
  if (!pet) return null;

  async function run(request: Promise<Result<Me>>, onDone: () => void) {
    setBusy(true);
    setMessage(null);
    const result = await request;
    setBusy(false);
    if (result.ok) {
      onMe(result.data);
      onDone();
    } else if (result.status === 401) {
      onUnauthorized();
    } else {
      setMessage(errorText(result.code));
    }
  }

  const buy = (item: Item) =>
    run(call(api.POST('/api/pet/buy', { body: { item: item.key } })), () => setReaction({ item: item.key, text: item.line }));
  const wear = (item: Item, worn: boolean) =>
    run(call(api.POST('/api/pet/wear', { body: { item: item.key, worn } })), () =>
      setReaction(worn ? { item: item.key, text: item.line } : null),
    );

  return (
    <main className="screen">
      <BackLink onBack={onBack} />
      <section className="nest">
        <PetView pet={pet} />
        <Growth pet={pet} />
      </section>

      <section className="card">
        <h2>{texts.pet.stages}</h2>
        <ul className="list plain">
          {pet.stages.map((stage) => (
            <li key={stage.key} className={stage.reached ? undefined : 'muted'}>
              {stage.reached ? '✓' : '○'} {stage.name} <span className="muted small">— {texts.pet.stageSparks(stage.sparks)}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>{texts.pet.character}</h2>
        <p className="muted small">{texts.pet.characterHint}</p>
        <ul className="list">
          {pet.traits.map((trait) => (
            <li key={trait.key}>
              <b>{trait.name}</b> {trait.value}{' '}
              <span className="muted small">
                · {trait.next_at === null ? texts.pet.allHabits : texts.pet.nextHabit(trait.next_at)}
              </span>
            </li>
          ))}
        </ul>
        <h3>{texts.pet.habits}</h3>
        {pet.habits.length > 0 ? (
          <ul className="list">
            {pet.habits.map((habit) => (
              <li key={habit.text}>
                {habit.text} <span className="muted small">· {habit.trait}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted small">{texts.pet.noHabits}</p>
        )}
      </section>

      <section className="card">
        <h2>{texts.pet.wardrobe}</h2>
        <p className="muted small">{texts.pet.balance(pet.sparks)}</p>
        {pet.slots.map((slot) => (
          <div key={slot.key} className="stack">
            <h3>{slot.name}</h3>
            {pet.items
              .filter((item) => item.slot === slot.key)
              .map((item) => (
                <ItemRow
                  key={item.key}
                  item={item}
                  pet={pet}
                  open={open === item.key}
                  busy={busy}
                  reaction={reaction?.item === item.key ? reaction.text : null}
                  onToggle={() => setOpen(open === item.key ? null : item.key)}
                  onBuy={() => void buy(item)}
                  onWear={(worn) => void wear(item, worn)}
                />
              ))}
          </div>
        ))}
        {message && <p className="message">{message}</p>}
      </section>
    </main>
  );
}

type ItemRowProps = {
  item: Item;
  pet: PetData;
  open: boolean;
  busy: boolean;
  reaction: string | null;
  onToggle: () => void;
  onBuy: () => void;
  onWear: (worn: boolean) => void;
};

/** Предмет: строка со статусом; раскрытый — примерка на питомце и действия. */
function ItemRow({ item, pet, open, busy, reaction, onToggle, onBuy, onWear }: ItemRowProps) {
  const status =
    item.state === 'owned'
      ? item.worn
        ? texts.pet.worn
        : texts.pet.owned
      : item.state === 'available'
        ? texts.pet.price(item.price)
        : texts.pet.locked;
  return (
    <div className="item">
      <button className={open ? 'option item-head selected' : 'option item-head'} aria-expanded={open} onClick={onToggle}>
        <span>{item.name}</span>
        <span className="muted small">{status}</span>
      </button>
      {open && (
        <div className="item-body">
          <PetView pet={pet} tryOn={item.key} small />
          <div className="stack">
            {reaction && <p className="bubble">{reaction}</p>}
            {item.state === 'locked' && <p className="muted small">{requirement(item)}</p>}
            {item.state === 'available' &&
              (pet.sparks >= item.price ? (
                <button className="button" disabled={busy} onClick={onBuy}>
                  {texts.pet.buy(item.price)}
                </button>
              ) : (
                <p className="muted small">
                  {texts.pet.notEnough} {texts.pet.price(item.price)}
                </p>
              ))}
            {item.state === 'owned' && (
              <button className="button secondary" disabled={busy} onClick={() => onWear(!item.worn)}>
                {item.worn ? texts.pet.takeOff : texts.pet.wear}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function requirement(item: Item): string {
  if (item.requires_stage) return texts.pet.requiresStage(item.requires_stage);
  if (item.requires_trait) return texts.pet.requiresTrait(item.requires_trait.name, item.requires_trait.at);
  return '';
}
