self.addEventListener('install', (event) => {
	event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
	event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
	if (!event.data) {
		return;
	}

	let payload = {};
	try {
		payload = event.data.json();
	} catch {
		payload = { title: 'newsy', body: event.data.text() };
	}

	const title = payload.title || 'newsy';
	const options = {
		body: payload.body || '',
		icon: '/favicon.svg',
		badge: '/favicon.svg',
		tag: payload.tag || 'newsy-notification',
		data: {
			url: payload.url || '/feeds'
		}
	};

	event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
	event.notification.close();
	const targetUrl = event.notification.data?.url || '/feeds';

	event.waitUntil(
		self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
			for (const client of clients) {
				if ('focus' in client) {
					client.navigate(targetUrl);
					return client.focus();
				}
			}

			if (self.clients.openWindow) {
				return self.clients.openWindow(targetUrl);
			}

			return undefined;
		})
	);
});
