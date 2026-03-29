import type { PageServerLoad } from './$types.js';

type FeedArticle = {
	title: string;
	link: string;
	description: string;
	thumbnail: string;
	published: string;
	published_datetime: string;
	source: string;
	starred: boolean;
	category: string;
	is_read?: boolean;
};

type FeedResponse = {
	articles: FeedArticle[];
	total: number;
	limit: number;
	offset: number;
	has_more: boolean;
};

type CategorySummary = {
	id: number;
	name: string;
	priority: number;
	ai_enabled: boolean;
	unread_count: number;
	total_count: number;
};

type ReportSchedule = {
	id: number;
	category: string;
	schedule_type: 'daily' | 'weekly';
	schedule_hour: number;
	schedule_minute: number;
	enabled: boolean;
	created_at: string | null;
	updated_at: string | null;
};

type ReportFile = {
	filename: string;
	category: string;
	report_type: string;
	generated_at: string;
	file_size: number;
	path: string;
};

function safeDateValue(value: string | undefined) {
	return value ? new Date(value).getTime() || 0 : 0;
}

function withReadState(articles: FeedArticle[], statuses: Record<string, boolean>) {
	return articles.map((article) => ({
		...article,
		is_read: Boolean(statuses[article.link])
	}));
}

function formatScheduleLabel(schedule: ReportSchedule | null) {
	if (!schedule) return null;
	const hour = String(schedule.schedule_hour ?? 0).padStart(2, '0');
	const minute = String(schedule.schedule_minute ?? 0).padStart(2, '0');
	return `${schedule.schedule_type === 'weekly' ? 'Weekly' : 'Daily'} • ${schedule.category} • ${hour}:${minute}`;
}

export const load: PageServerLoad = async ({ fetch, parent }) => {
	const { auth } = await parent();

	if (!auth.isAuthenticated) {
		return { home: null };
	}

	try {
		const [articlesRes, starredRes, categoriesRes, filesRes, schedulesRes] = await Promise.all([
			fetch('/api/feeds?limit=30&offset=0'),
			fetch('/api/feeds?limit=6&offset=0&starred_only=true'),
			fetch('/api/categories'),
			fetch('/api/reports/files'),
			fetch('/api/reports/schedules')
		]);

		const articlesPayload: FeedResponse = articlesRes.ok
			? await articlesRes.json()
			: { articles: [], total: 0, limit: 30, offset: 0, has_more: false };
		const starredPayload: FeedResponse = starredRes.ok
			? await starredRes.json()
			: { articles: [], total: 0, limit: 6, offset: 0, has_more: false };
		const categories: CategorySummary[] = categoriesRes.ok ? await categoriesRes.json() : [];
		const reportFiles: ReportFile[] = filesRes.ok ? await filesRes.json() : [];
		const schedules: ReportSchedule[] = schedulesRes.ok ? await schedulesRes.json() : [];

		const links = Array.from(
			new Set([
				...articlesPayload.articles.map((article) => article.link),
				...starredPayload.articles.map((article) => article.link)
			])
		);

		const statusesRes = links.length
			? await fetch('/api/articles/statuses', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ links })
				})
			: null;
		const statuses: Record<string, boolean> = statusesRes?.ok ? await statusesRes.json() : {};

		const decoratedArticles = withReadState(articlesPayload.articles, statuses);
		const decoratedStarred = withReadState(starredPayload.articles, statuses);
		const activeCategories = categories.filter(
			(category) => category.total_count > 0 || category.unread_count > 0
		);
		const latestStories = [...decoratedArticles].sort(
			(a, b) => safeDateValue(b.published_datetime) - safeDateValue(a.published_datetime)
		);

		return {
			home: {
				hasFeeds: categories.length > 0,
				unreadCount: activeCategories.reduce((total, category) => total + category.unread_count, 0),
				recentCount: activeCategories.reduce((total, category) => total + category.total_count, 0),
				categoryCount: categories.length,
				latestStories,
				hasMoreLatest: articlesPayload.has_more,
				savedStories: decoratedStarred.slice(0, 6),
				categoryPulse: [...activeCategories]
					.sort((a, b) => {
						if (b.unread_count !== a.unread_count) return b.unread_count - a.unread_count;
						return b.total_count - a.total_count;
					})
					.slice(0, 8),
				discoveryCategories: categories.map((category) => ({
					id: category.id,
					name: category.name
				})),
				latestReport: reportFiles[0] ?? null,
				nextSchedule: formatScheduleLabel(schedules.find((schedule) => schedule.enabled) ?? null)
			}
		};
	} catch (error) {
		console.error('Failed to load home briefing', error);
		return {
			home: {
				hasFeeds: false,
				unreadCount: 0,
				recentCount: 0,
				categoryCount: 0,
				latestStories: [],
				hasMoreLatest: false,
				savedStories: [],
				categoryPulse: [],
				discoveryCategories: [],
				latestReport: null,
				nextSchedule: null
			}
		};
	}
};
