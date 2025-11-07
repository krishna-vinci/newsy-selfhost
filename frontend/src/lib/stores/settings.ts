import { writable } from 'svelte/store';

export type Settings = {
	timezone: string;
};

const defaultSettings: Settings = {
	timezone: 'Asia/Kolkata'
};

function createSettingsStore() {
	const { subscribe, set, update } = writable<Settings>(defaultSettings);

	return {
		subscribe,
		set,
		update,
		async load() {
			try {
				const response = await fetch('/api/settings');
				if (!response.ok) {
					throw new Error('Failed to load settings');
				}
				const settings = await response.json();
				set(settings);
			} catch (error) {
				console.error('Error loading settings:', error);
				set(defaultSettings);
			}
		},
		async updateTimezone(timezone: string) {
			try {
				const response = await fetch('/api/settings', {
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ timezone })
				});

				if (!response.ok) {
					throw new Error('Failed to update timezone');
				}

				update(s => ({ ...s, timezone }));
				return true;
			} catch (error) {
				console.error('Error updating timezone:', error);
				return false;
			}
		}
	};
}

export const settings = createSettingsStore();
