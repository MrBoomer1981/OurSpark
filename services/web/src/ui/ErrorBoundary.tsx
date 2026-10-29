import { Component, type ReactNode } from 'react';

import { texts } from '../texts';
import { Icon } from './Icon';

type Props = { children: ReactNode };
type State = { crashed: boolean };

/** Экран упал при отрисовке — вместо пустой страницы объяснение и «Перезапустить». Ошибку React сам пишет в консоль. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { crashed: false };

  static getDerivedStateFromError(): State {
    return { crashed: true };
  }

  render() {
    if (!this.state.crashed) return this.props.children;
    return (
      <main className="screen center">
        <Icon name="habit" scale={5} />
        <h1 className="title">{texts.appName}</h1>
        <p className="muted">{texts.crash.text}</p>
        <button className="button" onClick={() => window.location.reload()}>
          {texts.crash.restart}
        </button>
      </main>
    );
  }
}
