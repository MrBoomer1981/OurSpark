import { addToHomeScreen, checkHomeScreenStatus } from '@tma.js/sdk-react';

import { launch } from '.';

/** Как предложить поставить гнездо на экран телефона. */
export type InstallOffer =
  | 'telegram' // Mini App: ярлык через Telegram (addToHomeScreen)
  | 'prompt' // браузер с beforeinstallprompt (Android, Chrome): своя кнопка «Установить»
  | 'ios' // браузеры iOS: только подсказка «Поделиться → На экран „Домой“»
  | null; // уже установлено или не поддерживается

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
}

let deferred: BeforeInstallPromptEvent | null = null;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((listener) => listener());

window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault(); // своя кнопка вместо баннера браузера
  deferred = event as BeforeInstallPromptEvent;
  notify();
});
window.addEventListener('appinstalled', () => {
  deferred = null;
  notify();
});

export function onInstallChange(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function standalone(): boolean {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

function ios(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

export async function installOffer(): Promise<InstallOffer> {
  if (launch.mode === 'telegram') {
    if (!checkHomeScreenStatus.isAvailable()) return null;
    try {
      const status = await checkHomeScreenStatus();
      return status === 'added' || status === 'unsupported' ? null : 'telegram';
    } catch {
      return null;
    }
  }
  if (standalone()) return null;
  if (deferred) return 'prompt';
  return ios() ? 'ios' : null;
}

export async function install(offer: InstallOffer): Promise<void> {
  if (offer === 'telegram') {
    addToHomeScreen.ifAvailable();
  } else if (offer === 'prompt' && deferred) {
    await deferred.prompt();
    deferred = null;
    notify();
  }
}
