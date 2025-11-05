import type { PageLoad } from './$types.js';

export const load: PageLoad = async ({ fetch }) => {
	try {
		const response = await fetch('/api/trends?source=youtube');
		if (!response.ok) {
			throw new Error(`Failed to fetch trends: ${response.statusText}`);
		}
		const data = await response.json();
		return {
			trends: data
		};
	} catch (error) {
		console.error('Error loading trends:', error);
		return {
			trends: { source: 'youtube', channels: [] },
			error: error instanceof Error ? error.message : 'Failed to load trends'
		};
	}
};
