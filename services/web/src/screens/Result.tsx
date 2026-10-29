import type { CSSProperties } from 'react';

import type { Me } from '../api/client';
import { PetView } from '../pet/PetView';
import { texts } from '../texts';
import { BackLink } from '../ui/BackLink';
import { Icon } from '../ui/Icon';

type Props = { me: Me; onBack: () => void };
type ResultData = NonNullable<NonNullable<Me['prompt']>['result']>;
type News = ResultData['news'][number];
type Answer = ResultData['partner'];

// Куда разлетаются искры от питомца: сдвиг и задержка каждой.
const BURST = [
  { dx: '-72px', dy: '-56px', delay: '0ms' },
  { dx: '68px', dy: '-64px', delay: '120ms' },
  { dx: '-88px', dy: '8px', delay: '240ms' },
  { dx: '84px', dy: '0px', delay: '60ms' },
  { dx: '-40px', dy: '-92px', delay: '300ms' },
  { dx: '36px', dy: '-96px', delay: '180ms' },
];

/** Результат: оба ответа (и прогнозы), общая реакция питомца, что получила пара и что у неё открылось. */
export function Result({ me, onBack }: Props) {
  const prompt = me.prompt;
  const result = prompt?.result;
  if (!prompt || !result || !prompt.mine) return null;
  const partnerName = me.pair?.partner?.name ?? '';
  const shifts = result.traits.map((t) => texts.result.shift(t.name, t.delta));

  return (
    <main className="screen">
      <BackLink onBack={onBack} />
      <section className="nest">
        <div className="pet-stage">
          {me.pet && <PetView pet={me.pet} cheer />}
          {result.sparks > 0 && (
            <div className="burst">
              {BURST.map((spark) => (
                <Icon
                  key={`${spark.dx}:${spark.dy}`}
                  name="spark"
                  // направление и задержка — переменными для анимации в index.css
                  style={{ '--dx': spark.dx, '--dy': spark.dy, '--delay': spark.delay } as CSSProperties}
                />
              ))}
            </div>
          )}
        </div>
        <p className="bubble">{result.line}</p>
      </section>
      <section className="card parchment gilded">
        <Icon name="seal" scale={3} className="seal" />
        <p className="muted small">{prompt.card.text}</p>
        <AnswerLine who={texts.result.you} answer={prompt.mine} />
        <AnswerLine who={partnerName} answer={result.partner} />
        {result.my_guess && (
          <p className="small">
            {texts.result.myGuess}: {result.my_guess.text} — <Verdict correct={result.my_guess.correct} />
          </p>
        )}
        {result.partner_guess && (
          <p className="small">
            <b>{partnerName}</b> {texts.result.partnerGuess}: {result.partner_guess.text} —{' '}
            <Verdict correct={result.partner_guess.correct} />
          </p>
        )}
      </section>
      <section className="card">
        <p className="reward">
          <Icon name="spark" />
          {texts.result.sparks(result.sparks)}
        </p>
        {shifts.length > 0 && <p className="muted small center-text">{shifts.join(' · ')}</p>}
      </section>
      {(result.news.length > 0 || result.chronicle) && (
        <section className="card">
          <h2>{texts.result.news}</h2>
          {result.news.map((news) => (
            <div key={`${news.kind}:${news.name}:${news.text}`} className="entry">
              <Icon name={news.kind} scale={3} />
              <div className="stack">
                <p>
                  <b>{newsTitle(news)}</b>
                </p>
                {news.text && <p className="muted small">{news.text}</p>}
              </div>
            </div>
          ))}
          {result.chronicle && (
            <div className="entry">
              <Icon name="page" scale={3} />
              <div className="stack">
                <p>
                  <b>{texts.result.chronicle}</b>
                </p>
                <p className="muted small">{result.chronicle}</p>
              </div>
            </div>
          )}
        </section>
      )}
      <button className="button" onClick={onBack}>
        {texts.result.toNest}
      </button>
      <p className="muted small center-text">{texts.prompt.tomorrow}</p>
    </main>
  );
}

function newsTitle(news: News): string {
  if (news.kind === 'stage') return texts.result.stage(news.name);
  if (news.kind === 'habit') return texts.result.habit(news.name);
  return texts.result.relic(news.name);
}

function Verdict({ correct }: { correct: boolean }) {
  return <span className={correct ? 'hit' : 'miss'}>{correct ? texts.result.guessed : texts.result.missed}</span>;
}

/** Ответ одного из пары: вариант строкой, свободный текст — отдельным абзацем, как написан. */
function AnswerLine({ who, answer }: { who: string; answer: Answer }) {
  if (answer.option === null) {
    return (
      <div>
        <p>
          <b>{who}</b>:
        </p>
        <p className="quote">{answer.text}</p>
      </div>
    );
  }
  return (
    <p>
      <b>{who}</b>: {answer.text}
    </p>
  );
}
