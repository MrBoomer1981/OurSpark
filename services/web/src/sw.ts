/// <reference lib="webworker" />
// Service worker гнезда: кеш приложения для PWA и web push. Регистрируется только вне Telegram (main.tsx).
import { clientsClaim } from 'workbox-core';
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute, type PrecacheEntry } from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';

import { texts } from './texts';

declare const self: ServiceWorkerGlobalScope & { __WB_MANIFEST: Array<PrecacheEntry | string> };

// Новая версия сразу берёт управление — без «закройте все вкладки».
void self.skipWaiting();
clientsClaim();

cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);
// Любой адрес приложения открывается из кеша, кроме запросов к api.
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html'), { denylist: [/^\/api\//] }));

type PushPayload = { title?: string; body?: string; url?: string };

self.addEventListener('push', (event) => {
  const data: PushPayload = event.data?.json() ?? {};
  event.waitUntil(
    self.registration.showNotification(data.title ?? texts.appName, {
      body: data.body,
      icon: '/icons/icon-192.png',
      data: { url: data.url ?? '/' },
    }),
  );
});

// Нажали на уведомление: открытое гнездо выходит вперёд, иначе открывается новое.
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url: string = event.notification.data?.url ?? '/';
  event.waitUntil(
    (async () => {
      const [open] = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      if (open) await open.focus();
      else await self.clients.openWindow(url);
    })(),
  );
});
