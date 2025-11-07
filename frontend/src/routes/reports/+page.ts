import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	try {
		const [schedulesRes, filesRes, categoriesRes] = await Promise.all([
			fetch('/api/reports/schedules'),
			fetch('/api/reports/files'),
			fetch('/api/categories')
		]);

		const schedules = schedulesRes.ok ? await schedulesRes.json() : [];
		const files = filesRes.ok ? await filesRes.json() : [];
		const categories = categoriesRes.ok ? await categoriesRes.json() : [];

		return {
			schedules,
			files,
			categories
		};
	} catch (error) {
		console.error('Error loading reports data:', error);
		return {
			schedules: [],
			files: [],
			categories: []
		};
	}
};
