import { useEffect, useState } from 'react';

import { api, call, type Me } from '../api/client';
import type { components } from '../api/schema';
import { texts } from '../texts';
import { BackLink } from '../ui/BackLink';
import { Icon } from '../ui/Icon';

type Entry = components['schemas']['ChronicleEntryView'];

// Иконка записи по её виду; совпавший выбор и всё незнакомое — страница летописи.
const ENTRY_ICONS: Record<string, string> = { hatch: 'hatch', stage: 'stage', habit: 'habit', relic: 'relic' };

type Props = { me: Me; onUnauthorized: () => void; onBack: () => void };

/** Летопись и коллекция: записи от новых к старым, реликвии, открытая косметика. */
export function Chronicle({ me, onUnauthorized, onBack }: Props) {
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [failed, setFailed] = useState(false);

  // Записей со временем много, поэтому их нет в /me: летопись грузится, когда её открывают.
  useEffect(() => {
    let alive = true;
    void call(api.GET('/api/chronicle')).then((result) => {
      if (!alive) return;
      if (result.ok) setEntries(result.data.entries);
      else if (result.status === 401) onUnauthorized();
      else setFailed(true);
    });
    return () => {
      alive = false;
    };
  }, [onUnauthorized]);

  const pet = me.pet;
  const owned = pet?.items.filter((item) => item.state === 'owned') ?? [];

  return (
    <main className="screen">
      <BackLink onBack={onBack} />
      <section className="card">
        <h2 className="with-icon">
          <Icon name="chronicle" />
          {texts.chronicle.title}
        </h2>
        {entries === null ? (
          <p className="muted">{failed ? texts.chronicle.failed : texts.chronicle.loading}</p>
        ) : (
          <ol className="list plain">
            {entries.map((entry) => (
              <li key={entry.id} className="entry">
                <Icon name={ENTRY_ICONS[entry.kind] ?? 'page'} />
                <span>
                  <span className="muted small">{date(entry.created_at)}</span>
                  <br />
                  {entry.text}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>
      {pet && (
        <section className="card">
          <h2>{texts.chronicle.relics}</h2>
          <p className="muted small">{texts.chronicle.relicsHint}</p>
          <ul className="list plain">
            {pet.relics.map((relic) =>
              relic.found ? (
                <li key={relic.name} className="entry">
                  <Icon name="relic" />
                  <span>
                    <b>{relic.name}</b>
                    <br />
                    <span className="muted small">{relic.text}</span>
                  </span>
                </li>
              ) : (
                <li key={relic.name} className="entry locked muted">
                  <Icon name="relic" />
                  <span>{texts.chronicle.relicProgress(relic.theme, relic.progress, relic.needed)}</span>
                </li>
              ),
            )}
          </ul>
        </section>
      )}
      {pet && (
        <section className="card">
          <h2>{texts.chronicle.wardrobe}</h2>
          {owned.length > 0 ? (
            <ul className="list">
              {owned.map((item) => (
                <li key={item.key}>{item.name}</li>
              ))}
            </ul>
          ) : (
            <p className="muted small">{texts.chronicle.noItems}</p>
          )}
        </section>
      )}
    </main>
  );
}

function date(iso: string): string {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
}
