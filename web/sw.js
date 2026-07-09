importScripts('notification-icons.js?v=4');

self.addEventListener('install', event => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', event => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', event => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (_err) {
    payload = {};
  }

  const title = payload.title || 'Herdr agent blocked';
  const options = {
    body: payload.body || 'An agent needs approval.',
    tag: payload.tag || 'herdr-blocked',
    renotify: true,
    icon: HERDR_NOTIFICATION_ICON,
    badge: HERDR_NOTIFICATION_BADGE,
    data: {
      url: payload.url || './',
    },
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = new URL(event.notification.data && event.notification.data.url || './', self.location.origin + '/').href;

  // One action per click: the click's user activation only reliably funds a
  // single focus/openWindow call, so never chain attempts. A visible window
  // gets focused and routed in place; everything else (hidden, frozen, or no
  // client) goes straight to openWindow, which launches/raises the installed
  // PWA on Android.
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({type: 'window', includeUncontrolled: true});
    const visible = windows.find(client =>
      client.url.startsWith(self.location.origin) && client.visibilityState === 'visible');
    if (visible) {
      try {
        visible.postMessage({type: 'herdr_notification_click', url});
      } catch (_err) {}
      try {
        await visible.focus();
      } catch (_err) {}
      return;
    }
    await self.clients.openWindow(url);
  })());
});
