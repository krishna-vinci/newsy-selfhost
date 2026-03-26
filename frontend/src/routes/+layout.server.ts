import { redirect } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';

const PUBLIC_PATHS = new Set(['/login', '/signup', '/bootstrap']);

export const load = async ({ fetch, url }: RequestEvent) => {
	const configResponse = await fetch('/api/auth/config');
	const authConfig = configResponse.ok
		? await configResponse.json()
		: { bootstrap_required: false, allow_public_signup: false };

	let user = null;
	const meResponse = await fetch('/api/auth/me');
	if (meResponse.ok) {
		user = await meResponse.json();
	}

	const currentPath = url.pathname;
	const nextTarget = `${url.pathname}${url.search}`;

	if (authConfig.bootstrap_required && currentPath !== '/bootstrap') {
		throw redirect(303, '/bootstrap');
	}

	if (!authConfig.bootstrap_required && currentPath === '/bootstrap') {
		throw redirect(303, user ? '/' : '/login');
	}

	if (
		currentPath === '/signup' &&
		!authConfig.allow_public_signup &&
		!authConfig.bootstrap_required
	) {
		throw redirect(303, '/login');
	}

	if (!user && !PUBLIC_PATHS.has(currentPath)) {
		throw redirect(303, `/login?next=${encodeURIComponent(nextTarget)}`);
	}

	if (
		user &&
		(currentPath === '/login' || currentPath === '/signup' || currentPath === '/bootstrap')
	) {
		const requestedNext = url.searchParams.get('next');
		throw redirect(303, requestedNext || '/');
	}

	return {
		auth: {
			user,
			isAuthenticated: Boolean(user),
			isAdmin: user?.role === 'admin',
			allowPublicSignup: Boolean(authConfig.allow_public_signup),
			bootstrapRequired: Boolean(authConfig.bootstrap_required)
		}
	};
};
