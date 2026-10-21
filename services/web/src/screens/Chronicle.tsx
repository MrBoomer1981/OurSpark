import { useEffect, useState } from 'react';

import { api, call, type Me } from '../api/client';
import type { components } from '../api/schema';
import { texts } from '../texts';
import { BackLink } from '../ui/BackLink';

type Entry = components['schemas']['ChronicleEntryView'];

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
        <h2>{texts.chronicle.title}</h2>
        {entries === null ? (
          <p className="muted">{failed ? texts.chronicle.failed : texts.chronicle.loading}</p>
        ) : (
          <ol className="list plain">
            {entries.map((entry) => (
              <li key={entry.id}>
                <span className="muted small">{date(entry.created_at)}</span>
                <br />
                {entry.text}
              </li>
            ))}
          </ol>
        )}
      </section>
      {pet && (
        <section className="card">
          <h2>{texts.chronicle.relics}</h2>
          <p className="muted small">{texts.chronicle.relicsHint}</p>
          <ul className="list">
            {pet.relics.map((relic) =>
              relic.found ? (
                <li key={relic.name}>
                  <b>{relic.name}</b>
                  <br />
                  <span className="muted small">{relic.text}</span>
                </li>
              ) : (
                <li key={relic.name} className="muted">
                  {texts.chronicle.relicProgress(relic.theme, relic.progress, relic.needed)}
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
