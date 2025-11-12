import type { PageLoad } from './$types.js';

export const load: PageLoad = async () => {
	// Client-side handles all data loading via loadInitialArticles()
	// This eliminates blocking server-side fetch for faster initial page render
	return {
		categories: []
	};
};
