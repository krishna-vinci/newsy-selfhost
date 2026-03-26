// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		interface Locals {
			user?: {
				id: number;
				username: string;
				email: string | null;
				role: 'admin' | 'user';
				is_active: boolean;
				created_at: string | null;
				last_login_at: string | null;
			} | null;
		}
		interface PageData {
			auth: {
				user: Locals['user'];
				isAuthenticated: boolean;
				isAdmin: boolean;
				allowPublicSignup: boolean;
				bootstrapRequired: boolean;
			};
		}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
