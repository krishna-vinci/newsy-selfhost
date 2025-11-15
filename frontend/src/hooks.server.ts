import type { Handle } from '@sveltejs/kit';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8765';

export const handle: Handle = async ({ event, resolve }) => {
	// Proxy API requests to the backend
	if (event.url.pathname.startsWith('/api')) {
		const targetUrl = `${API_BASE_URL}${event.url.pathname}${event.url.search}`;

		try {
			// For file uploads (multipart/form-data), we need to read the body as arrayBuffer
			// to preserve the binary data and boundary markers
			let body: BodyInit | undefined = undefined;
			
			if (event.request.method !== 'GET' && event.request.method !== 'HEAD') {
				// Read the body as arrayBuffer to preserve binary data for file uploads
				body = await event.request.arrayBuffer();
			}

			const proxiedRequest = new Request(targetUrl, {
				method: event.request.method,
				headers: event.request.headers,
				body: body,
				redirect: 'manual'
			});

			const response = await fetch(proxiedRequest);

			// Return the response as-is
			return new Response(response.body, {
				status: response.status,
				statusText: response.statusText,
				headers: response.headers
			});
		} catch (error) {
			console.error('Proxy error:', error);
			return new Response(JSON.stringify({ error: 'Failed to connect to backend API' }), {
				status: 502,
				headers: { 'Content-Type': 'application/json' }
			});
		}
	}

	return resolve(event);
};
