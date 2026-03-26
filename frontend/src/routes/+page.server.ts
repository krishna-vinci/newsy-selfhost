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

function selectPriorityStories(articles: FeedArticle[], limit = 6) {
	const sorted = [...articles].sort((a, b) => {
		const readScore = Number(Boolean(a.is_read)) - Number(Boolean(b.is_read));
		if (readScore !== 0) return readScore;
		return safeDateValue(b.published_datetime) - safeDateValue(a.published_datetime);
	});

	const selected: FeedArticle[] = [];
	const usedSources = new Set<string>();
	const usedCategories = new Set<string>();

	for (const article of sorted) {
		if (selected.length >= limit) break;
		if (usedSources.has(article.source) || usedCategories.has(article.category)) continue;
		selected.push(article);
		usedSources.add(article.source);
		usedCategories.add(article.category);
	}

	for (const article of sorted) {
		if (selected.length >= limit) break;
		if (selected.some((item) => item.link === article.link)) continue;
		selected.push(article);
	}

	return selected;
}

function buildDigest(
	categories: CategorySummary[],
	priorityStories: FeedArticle[],
	aiEnabled: boolean
) {
	const activeCategories = categories.filter(
		(category) => category.unread_count > 0 || category.total_count > 0
	);
	const unreadCount = activeCategories.reduce(
		(total, category) => total + category.unread_count,
		0
	);
	const recentCount = activeCategories.reduce((total, category) => total + category.total_count, 0);
	const topCategory =
		[...activeCategories]
			.filter((category) => category.unread_count > 0)
			.sort((a, b) => b.unread_count - a.unread_count)[0] ?? null;
	const topSources = Array.from(
		new Set(priorityStories.map((story) => story.source).filter(Boolean))
	).slice(0, 3);

	const summary = topCategory
		? `${topCategory.name} is setting the pace right now, with ${topCategory.unread_count} unread item${topCategory.unread_count === 1 ? '' : 's'} ready for a closer look.`
		: unreadCount > 0
			? `${unreadCount} unread item${unreadCount === 1 ? '' : 's'} are waiting across your reading desk.`
			: 'You are caught up for now, so this is a good moment to revisit saved stories or open a report.';

	const bullets = [
		`${recentCount} recent item${recentCount === 1 ? '' : 's'} surfaced across ${activeCategories.length || 0} categor${activeCategories.length === 1 ? 'y' : 'ies'}.`,
		topSources.length > 0
			? `Top sources in view: ${topSources.join(', ')}.`
			: 'Your next stories will appear here as soon as your sources publish again.',
		priorityStories[0]
			? `Start with “${priorityStories[0].title}” if you want the quickest path back into the feed.`
			: 'Saved stories and reports are still close by if you want a slower pass.'
	];

	if (aiEnabled) {
		bullets.splice(
			2,
			0,
			'AI-assisted categories are active, so your deeper reading views can stay tighter when you switch to feeds.'
		);
	}

	return {
		title: "Today's pulse",
		summary,
		bullets: bullets.slice(0, 3)
	};
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
			fetch('/api/feeds?limit=18&offset=0'),
			fetch('/api/feeds?limit=5&offset=0&starred_only=true'),
			fetch('/api/categories'),
			fetch('/api/reports/files'),
			fetch('/api/reports/schedules')
		]);

		const articlesPayload: FeedResponse = articlesRes.ok
			? await articlesRes.json()
			: { articles: [], total: 0, limit: 18, offset: 0, has_more: false };
		const starredPayload: FeedResponse = starredRes.ok
			? await starredRes.json()
			: { articles: [], total: 0, limit: 5, offset: 0, has_more: false };
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
		const aiEnabled = activeCategories.some((category) => category.ai_enabled);

		return {
			home: {
				hasFeeds: categories.length > 0,
				unreadCount: activeCategories.reduce((total, category) => total + category.unread_count, 0),
				recentCount: activeCategories.reduce((total, category) => total + category.total_count, 0),
				categoryCount: activeCategories.length,
				aiEnabled,
				priorityStories: selectPriorityStories(decoratedArticles, 6),
				savedStories: decoratedStarred.slice(0, 5),
				categoryPulse: [...activeCategories]
					.sort((a, b) => b.unread_count - a.unread_count)
					.slice(0, 6),
				digest: buildDigest(activeCategories, decoratedArticles, aiEnabled),
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
				aiEnabled: false,
				priorityStories: [],
				savedStories: [],
				categoryPulse: [],
				digest: {
					title: "Today's pulse",
					summary: 'Your home view is taking a quiet moment. Open feeds to refresh the desk.',
					bullets: ['Move into feeds for a fuller reading pass whenever you are ready.']
				},
				latestReport: null,
				nextSchedule: null
			}
		};
	}
};
