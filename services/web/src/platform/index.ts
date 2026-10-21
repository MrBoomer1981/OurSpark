import {
  init,
  isTMA,
  miniApp,
  retrieveLaunchParams,
  retrieveRawInitData,
  viewport,
} from '@tma.js/sdk-react';

/** Режим запуска: внутри Telegram (есть параметры запуска с initData) или PWA — установленное или в браузере. */
export type Mode = 'telegram' | 'pwa';

/** Что известно о запуске. Заполняется один раз в initPlatform, до первого рендера. */
export const launch: { mode: Mode; initData?: string; startParam?: string } = { mode: 'pwa' };

/** Определяет режим и готовит окружение Telegram. */
export function initPlatform(): void {
  if (!isTMA()) return;
  init();
  launch.mode = 'telegram';
  launch.initData = retrieveRawInitData();
  launch.startParam = retrieveLaunchParams().tgWebAppStartParam;
  // Шапку и фон Telegram красим в цвет гнезда, чтобы над ним не было светлой полосы.
  const background = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
  miniApp.mount.ifAvailable();
  miniApp.setHeaderColor.ifAvailable(background);
  miniApp.setBgColor.ifAvailable(background);
  if (viewport.mount.isAvailable()) {
    viewport
      .mount()
      .then(() => viewport.expand.ifAvailable())
      .catch((error: unknown) => console.error(error));
  }
  miniApp.ready.ifAvailable();
}
