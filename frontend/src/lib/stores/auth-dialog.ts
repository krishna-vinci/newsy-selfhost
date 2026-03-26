import { writable } from 'svelte/store';

export type AuthMode = 'login' | 'signup';

type AuthDialogState = {
	open: boolean;
	mode: AuthMode;
	next: string | null;
};

const initialState: AuthDialogState = {
	open: false,
	mode: 'login',
	next: null
};

const store = writable<AuthDialogState>(initialState);

export const authDialog = {
	subscribe: store.subscribe
};

export function openAuthDialog(mode: AuthMode = 'login', next: string | null = null) {
	store.set({ open: true, mode, next });
}

export function closeAuthDialog() {
	store.update((state) => ({ ...state, open: false }));
}

export function setAuthDialogMode(mode: AuthMode) {
	store.update((state) => ({ ...state, mode }));
}
