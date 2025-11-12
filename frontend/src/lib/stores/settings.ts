import { writable } from 'svelte/store';

export type Settings = {
	timezone: string;
	default_view?: 'card' | 'headline' | 'column';
};

const defaultSettings: Settings = {
	timezone: 'Asia/Kolkata',
	default_view: 'card'
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
		},
		async updateDefaultView(default_view: 'card' | 'headline' | 'column') {
			try {
				const response = await fetch('/api/settings', {
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ default_view })
				});

				if (!response.ok) {
					throw new Error('Failed to update default view');
				}

				update(s => ({ ...s, default_view }));
				return true;
			} catch (error) {
				console.error('Error updating default view:', error);
				return false;
			}
		}
	};
}

export const settings = createSettingsStore();
