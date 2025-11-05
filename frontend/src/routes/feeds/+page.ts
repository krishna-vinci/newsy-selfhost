import type { PageLoad } from './$types.js';

export const load: PageLoad = async ({ fetch }) => {
	try {
		const response = await fetch('/api/feeds');
		if (!response.ok) {
			throw new Error(`Failed to fetch feeds: ${response.statusText}`);
		}
		const data = await response.json();
		return {
			categories: data
		};
	} catch (error) {
		console.error('Error loading feeds:', error);
		return {
			categories: [],
			error: error instanceof Error ? error.message : 'Failed to load feeds'
		};
	}
};
