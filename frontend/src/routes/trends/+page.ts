import type { PageLoad } from './$types.js';

export const load: PageLoad = async ({ fetch }) => {
	try {
		const [youtubeResponse, googleResponse, twitterResponse] = await Promise.all([
			fetch('/api/trends?source=youtube'),
			fetch('/api/trends?source=google'),
			fetch('/api/trends?source=twitter')
		]);

		if (!youtubeResponse.ok) {
			throw new Error(`Failed to fetch YouTube trends: ${youtubeResponse.statusText}`);
		}
		if (!googleResponse.ok) {
			throw new Error(`Failed to fetch Google trends: ${googleResponse.statusText}`);
		}
		if (!twitterResponse.ok) {
			throw new Error(`Failed to fetch Twitter feed: ${twitterResponse.statusText}`);
		}

		const youtubeData = await youtubeResponse.json();
		const googleData = await googleResponse.json();
		const twitterData = await twitterResponse.json();

		return {
			youtube: youtubeData,
			google: googleData,
			twitter: twitterData
		};
	} catch (error) {
		console.error('Error loading trends data:', error);
		return {
			youtube: null,
			google: null,
			twitter: null,
			error: error instanceof Error ? error.message : 'Failed to load trends data'
		};
	}
};
