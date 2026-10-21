import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import './index.css';
import { App } from './App';
import { initPlatform, launch } from './platform';
import { texts } from './texts';

document.title = texts.appName;
try {
  initPlatform();
} catch (error) {
  // Гнездо должно открыться, даже если Telegram ответил не так, как ждали.
  console.error(error);
}

if (launch.mode === 'pwa') {
  // Service worker — только вне Telegram: внутри Mini App он держал бы старую версию после деплоя.
  void import('virtual:pwa-register').then(({ registerSW }) => registerSW({ immediate: true }));
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
