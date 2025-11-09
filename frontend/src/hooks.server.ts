import type { Handle } from '@sveltejs/kit';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8321';

export const handle: Handle = async ({ event, resolve }) => {
	// Proxy API requests to the backend
	if (event.url.pathname.startsWith('/api') || event.url.pathname.startsWith('/article-full-text')) {
		const targetUrl = `${API_BASE_URL}${event.url.pathname}${event.url.search}`;
		
		try {
			const response = await fetch(targetUrl, {
				method: event.request.method,
				headers: event.request.headers,
				body: event.request.method !== 'GET' && event.request.method !== 'HEAD' 
					? await event.request.text() 
					: undefined
			});

			// Create a new response with the proxied data
			const responseBody = await response.text();
			return new Response(responseBody, {
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
