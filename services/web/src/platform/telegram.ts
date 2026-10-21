import { backButton, requestWriteAccess } from '@tma.js/sdk-react';
import { useEffect } from 'react';

import { launch } from '.';

/** Просит у человека разрешение боту писать ему. true — разрешил. */
export async function askWriteAccess(): Promise<boolean> {
  if (launch.mode !== 'telegram' || !requestWriteAccess.isAvailable()) return false;
  try {
    return (await requestWriteAccess()) === 'allowed';
  } catch {
    return false;
  }
}

/** Кнопка «назад» Telegram на вторичном экране. Вне Telegram экран рисует свою ссылку «назад». */
export function useBackButton(onBack: () => void): void {
  useEffect(() => {
    if (launch.mode !== 'telegram' || !backButton.show.isAvailable()) return;
    backButton.show();
    const off = backButton.onClick(onBack);
    return () => {
      off();
      backButton.hide.ifAvailable();
    };
  }, [onBack]);
}
