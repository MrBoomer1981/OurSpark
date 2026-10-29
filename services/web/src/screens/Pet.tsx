import { useEffect, useState } from 'react';

import { api, call, track, type Me } from '../api/client';
import { useAction } from '../api/useAction';
import { Bar, Growth } from '../pet/Growth';
import { PetView, type Pet as PetData } from '../pet/PetView';
import { texts } from '../texts';
import { BackLink } from '../ui/BackLink';
import { Icon } from '../ui/Icon';

type Item = PetData['items'][number];

type Props = {
  me: Me;
  onMe: (me: Me) => void;
  onUnauthorized: () => void;
  onStale: (code: string) => void;
  onBack: () => void;
};

/** Питомец: стадии, характер и привычки, косметика с примеркой. */
export function Pet({ me, onMe, onUnauthorized, onStale, onBack }: Props) {
  const [open, setOpen] = useState<string | null>(null); // раскрытый предмет — его и примеряем
  const [reaction, setReaction] = useState<{ item: string; text: string } | null>(null); // питомец об обнове
  const { run, pending, busy, message } = useAction({ onMe, onUnauthorized, onStale });
  useEffect(() => track('pet'), []);
  const pet = me.pet;
  if (!pet) return null;

  async function buy(item: Item) {
    if (await run(`buy:${item.key}`, call(api.POST('/api/pet/buy', { body: { item: item.key } })))) {
      setReaction({ item: item.key, text: item.line });
    }
  }

  async function wear(item: Item, worn: boolean) {
    if (await run(`wear:${item.key}`, call(api.POST('/api/pet/wear', { body: { item: item.key, worn } })))) {
      setReaction(worn ? { item: item.key, text: item.line } : null);
    }
  }

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
            <li key={stage.key} className={stage.reached ? 'entry' : 'entry locked muted'}>
              <Icon name="stage" />
              <span>
                {stage.name} <span className="muted small">— {texts.pet.stageSparks(stage.sparks)}</span>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>{texts.pet.character}</h2>
        <p className="muted small">{texts.pet.characterHint}</p>
        <ul className="list plain">
          {pet.traits.map((trait) => (
            <li key={trait.key} className="trait">
              <span className="trait-head">
                <b>{trait.name}</b>
                <span className="muted small">
                  {trait.next_at === null ? texts.pet.allHabits : texts.pet.nextHabit(trait.next_at)}
                </span>
              </span>
              <Bar value={trait.value} max={trait.next_at ?? trait.value} label={`${trait.name}: ${trait.value}`} kind="trait" />
            </li>
          ))}
        </ul>
        <h3>{texts.pet.habits}</h3>
        {pet.habits.length > 0 ? (
          <ul className="list plain">
            {pet.habits.map((habit) => (
              <li key={habit.text} className="entry">
                <Icon name="habit" />
                <span>
                  {habit.text} <span className="muted small">· {habit.trait}</span>
                </span>
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
                  pending={pending}
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
  pending: string | null; // какое действие сейчас идёт: buy:<предмет> или wear:<предмет>
  reaction: string | null;
  onToggle: () => void;
  onBuy: () => void;
  onWear: (worn: boolean) => void;
};

/** Предмет: строка со статусом; раскрытый — примерка на питомце и действия. */
function ItemRow({ item, pet, open, busy, pending, reaction, onToggle, onBuy, onWear }: ItemRowProps) {
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
                <button className="button" disabled={busy} aria-busy={pending === `buy:${item.key}`} onClick={onBuy}>
                  {texts.pet.buy(item.price)}
                </button>
              ) : (
                <p className="muted small">
                  {texts.pet.notEnough} {texts.pet.price(item.price)}
                </p>
              ))}
            {item.state === 'owned' && (
              <button
                className="button secondary"
                disabled={busy}
                aria-busy={pending === `wear:${item.key}`}
                onClick={() => onWear(!item.worn)}
              >
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
