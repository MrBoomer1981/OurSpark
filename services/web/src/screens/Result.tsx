import type { Me } from '../api/client';
import { PetView } from '../pet/PetView';
import { texts } from '../texts';
import { BackLink } from '../ui/BackLink';

type Props = { me: Me; onBack: () => void };
type ResultData = NonNullable<NonNullable<Me['prompt']>['result']>;
type News = ResultData['news'][number];
type Answer = ResultData['partner'];

/** Результат: оба ответа (и прогнозы), общая реакция питомца, что получила пара и что у неё открылось. */
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
        {me.pet && <PetView pet={me.pet} />}
        <p className="bubble">{result.line}</p>
      </section>
      <section className="card">
        <p className="muted small">{prompt.card.text}</p>
        <AnswerLine who={texts.result.you} answer={prompt.mine} />
        <AnswerLine who={partnerName} answer={result.partner} />
        {result.my_guess && (
          <p className="small">
            {texts.result.myGuess}: {result.my_guess.text} — {result.my_guess.correct ? texts.result.guessed : texts.result.missed}
          </p>
        )}
        {result.partner_guess && (
          <p className="small">
            <b>{partnerName}</b> {texts.result.partnerGuess}: {result.partner_guess.text} —{' '}
            {result.partner_guess.correct ? texts.result.guessed : texts.result.missed}
          </p>
        )}
        <p className="reward">{rewards.join(' · ')}</p>
      </section>
      {(result.news.length > 0 || result.chronicle) && (
        <section className="card">
          <h2>{texts.result.news}</h2>
          {result.news.map((news) => (
            <div key={`${news.kind}:${news.name}:${news.text}`}>
              <p>
                <b>{newsTitle(news)}</b>
              </p>
              {news.text && <p className="muted small">{news.text}</p>}
            </div>
          ))}
          {result.chronicle && (
            <div>
              <p>
                <b>{texts.result.chronicle}</b>
              </p>
              <p className="muted small">{result.chronicle}</p>
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
