import type { Handle } from '@sveltejs/kit';

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8765';
const REFRESH_COOKIE_NAME = process.env.AUTH_REFRESH_COOKIE_NAME || 'newsy_refresh_token';
const NON_REFRESHABLE_PATHS = new Set([
	'/api/auth/sign-in',
	'/api/auth/refresh',
	'/api/auth/sign-out',
	'/api/users',
	'/api/users/bootstrap'
]);

function getSetCookieValues(headers: Headers): string[] {
	const typedHeaders = headers as Headers & { getSetCookie?: () => string[] };
	if (typeof typedHeaders.getSetCookie === 'function') {
		return typedHeaders.getSetCookie();
	}

	const setCookie = headers.get('set-cookie');
	return setCookie ? [setCookie] : [];
}

function mergeCookieHeader(existingCookieHeader: string | null, setCookies: string[]): string {
	const cookieMap = new Map<string, string>();

	for (const part of (existingCookieHeader || '').split(';')) {
		const trimmed = part.trim();
		if (!trimmed) continue;
		const separatorIndex = trimmed.indexOf('=');
		if (separatorIndex === -1) continue;
		cookieMap.set(trimmed.slice(0, separatorIndex), trimmed.slice(separatorIndex + 1));
	}

	for (const setCookie of setCookies) {
		const [cookiePair, ...attributes] = setCookie.split(';');
		const separatorIndex = cookiePair.indexOf('=');
		if (separatorIndex === -1) continue;

		const name = cookiePair.slice(0, separatorIndex).trim();
		const value = cookiePair.slice(separatorIndex + 1);
		const shouldDelete = attributes.some((attribute) => {
			const normalized = attribute.trim().toLowerCase();
			return normalized === 'max-age=0' || normalized.startsWith('expires=thu, 01 jan 1970');
		});

		if (shouldDelete) {
			cookieMap.delete(name);
		} else {
			cookieMap.set(name, value);
		}
	}

	return Array.from(cookieMap.entries())
		.map(([name, value]) => `${name}=${value}`)
		.join('; ');
}

async function proxyApiRequest(
	targetUrl: string,
	request: Request,
	body: BodyInit | undefined,
	cookieHeaderOverride?: string
): Promise<Response> {
	const headers = new Headers(request.headers);
	if (cookieHeaderOverride !== undefined) {
		if (cookieHeaderOverride) {
			headers.set('cookie', cookieHeaderOverride);
		} else {
			headers.delete('cookie');
		}
	}

	return fetch(
		new Request(targetUrl, {
			method: request.method,
			headers,
			body,
			redirect: 'manual'
		})
	);
}

function buildProxyResponse(
	upstreamResponse: Response,
	additionalSetCookies: string[] = []
): Response {
	const headers = new Headers(upstreamResponse.headers);
	for (const setCookie of additionalSetCookies) {
		headers.append('set-cookie', setCookie);
	}

	return new Response(upstreamResponse.body, {
		status: upstreamResponse.status,
		statusText: upstreamResponse.statusText,
		headers
	});
}

export const handle: Handle = async ({ event, resolve }) => {
	if (event.url.pathname.startsWith('/api')) {
		const targetUrl = `${API_BASE_URL}${event.url.pathname}${event.url.search}`;

		try {
			let body: BodyInit | undefined = undefined;

			if (event.request.method !== 'GET' && event.request.method !== 'HEAD') {
				body = await event.request.arrayBuffer();
			}

			let response = await proxyApiRequest(targetUrl, event.request, body);

			if (
				response.status === 401 &&
				!NON_REFRESHABLE_PATHS.has(event.url.pathname) &&
				event.cookies.get(REFRESH_COOKIE_NAME)
			) {
				const refreshResponse = await fetch(
					new Request(`${API_BASE_URL}/api/auth/refresh`, {
						method: 'POST',
						headers: new Headers(event.request.headers),
						redirect: 'manual'
					})
				);

				if (refreshResponse.ok) {
					const refreshSetCookies = getSetCookieValues(refreshResponse.headers);
					const mergedCookieHeader = mergeCookieHeader(
						event.request.headers.get('cookie'),
						refreshSetCookies
					);
					response = await proxyApiRequest(targetUrl, event.request, body, mergedCookieHeader);
					return buildProxyResponse(response, refreshSetCookies);
				}
			}

			return buildProxyResponse(response);
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
