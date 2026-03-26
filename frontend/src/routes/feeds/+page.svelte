<script lang="ts">
	import type { PageData } from './$types.js';
	import { goto, invalidateAll } from '$app/navigation';
	import { page } from '$app/stores';
	import { onMount, onDestroy } from 'svelte';
	import {
		Copy,
		Eye,
		CheckCircle,
		Circle,
		LayoutGrid,
		List,
		Columns2,
		ExternalLink,
		Search,
		X,
		Star,
		FileText,
		Sparkles,
		ChevronUp,
		ChevronDown,
		HelpCircle,
		Bell
	} from '@lucide/svelte';
	import { toast } from 'svelte-sonner';
	import { copyToClipboard } from '$lib/utils/clipboard.ts';
	import Button from '$lib/components/ui/button/index.svelte';
	import Badge from '$lib/components/ui/badge/index.svelte';
	import Separator from '$lib/components/ui/separator/index.svelte';
	import Dialog from '$lib/components/ui/dialog/index.svelte';
	import Card from '$lib/components/ui/card/index.svelte';
	import Input from '$lib/components/ui/input/index.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import FeedSidebar from '$lib/components/FeedSidebar.svelte';
	import KeyboardShortcutsDialog from '$lib/components/KeyboardShortcutsDialog.svelte';
	import YoutubeEmbed from '$lib/components/YoutubeEmbed.svelte';
	import { settings } from '$lib/stores/settings.ts';

	let { data }: { data: PageData } = $props();

	let timezone = $state('UTC');

	function formatPublishedDate(dateString: string, tz: string): string {
		if (!dateString) return '';
		try {
			const date = new Date(dateString);
			return new Intl.DateTimeFormat('en-US', {
				year: 'numeric',
				month: 'short',
				day: 'numeric',
				hour: 'numeric',
				minute: '2-digit',
				timeZone: tz,
				hour12: true
			}).format(date);
		} catch (error) {
			console.warn(`Invalid timezone '${tz}' or date '${dateString}'. Falling back.`, error);
			try {
				return new Date(dateString).toLocaleString();
			} catch {
				return dateString;
			}
		}
	}

	type ViewMode = 'card' | 'headline' | 'column';
	type FeedItem = {
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
	type Category = {
		category: string;
		feed_items: FeedItem[];
	};

	// State
	let viewMode = $state<ViewMode>('card');
	let selectedCategory = $state<string>('all');
	let selectedFeedUrl = $state<string | null>(null);
	let selectedFeedName = $state<string | null>(null);
	let modalOpen = $state(false);
	let selectedArticle = $state<FeedItem | null>(null);
	let articleContent = $state<string>('');
	let isLoadingContent = $state(false);
	let selectedColumnIndex = $state<number>(0);
	let searchQuery = $state<string>('');
	let isSearching = $state(false);
	let searchTimeout: ReturnType<typeof setTimeout> | null = null;
	let searchResults = $state<Category[]>([]);
	let isSearchMode = $state<boolean>(false);
	let isStarredViewActive = $state<boolean>(false);
	let isGeneratingReport = $state<boolean>(false);
	let hideReadArticles = $state<boolean>(false);
	let readStatuses = $state<Record<string, boolean>>({});
	let viewType = $state<'standard' | 'ai'>('standard');

	// Pagination state
	let allArticles = $state<FeedItem[]>([]);
	let currentOffset = $state<number>(0);
	let hasMore = $state<boolean>(true);
	let isLoadingMore = $state<boolean>(false);
	let totalArticles = $state<number>(0);
	const INITIAL_LOAD = 100;
	const LOAD_MORE_SIZE = 50;

	// Summarization state
	let showSummaryModal = $state(false);
	let summaryArticle = $state<FeedItem | null>(null);
	let summaryText = $state<string>('');
	let isLoadingSummary = $state(false);

	// UI state
	let showShortcutsModal = $state(false);
	let showScrollToTop = $state(false);
	let scrollContainer: HTMLDivElement | null = null;

	// Search input reference for keyboard shortcuts
	let searchInputRef: HTMLInputElement | null = null;

	// Thumbnail fallback state
	let failedThumbnails = $state<Set<string>>(new Set());

	// Real-time updates state
	let lastCheckTimestamp = $state<string>(new Date().toISOString());
	let newArticlesCount = $state<number>(0);
	let newArticlesByCategory = $state<Record<string, number>>({});
	let updateCheckInterval: ReturnType<typeof setInterval> | null = null;
	let unsubscribe: () => void;

	function getFeedDisplayName(feedUrl: string | null): string | null {
		if (!feedUrl) {
			return null;
		}

		try {
			return new URL(feedUrl).hostname.replace(/^www\./, '');
		} catch {
			return feedUrl;
		}
	}

	function buildFeedsUrl(category: string, feedUrl: string | null) {
		const params = new URLSearchParams();

		if (feedUrl) {
			params.set('feed_url', feedUrl);
		} else if (category !== 'all') {
			params.set('category', category);
		}

		const query = params.toString();
		return query ? `/feeds?${query}` : '/feeds';
	}

	function applySelectionFromUrl() {
		const categoryParam = $page.url.searchParams.get('category');
		const feedUrlParam = $page.url.searchParams.get('feed_url');

		if (feedUrlParam) {
			const normalizedFeedUrl = decodeURIComponent(feedUrlParam);
			const didChange = selectedFeedUrl !== normalizedFeedUrl || selectedCategory !== 'all';

			selectedCategory = 'all';
			selectedFeedUrl = normalizedFeedUrl;
			selectedFeedName = getFeedDisplayName(normalizedFeedUrl);

			return didChange;
		}

		if (categoryParam) {
			const normalizedCategory = decodeURIComponent(categoryParam);
			const didChange = selectedCategory !== normalizedCategory || selectedFeedUrl !== null;

			selectedCategory = normalizedCategory;
			selectedFeedUrl = null;
			selectedFeedName = null;

			return didChange;
		}

		const didChange =
			selectedCategory !== 'all' || selectedFeedUrl !== null || selectedFeedName !== null;
		selectedCategory = 'all';
		selectedFeedUrl = null;
		selectedFeedName = null;

		return didChange;
	}

	function hasThumbnail(article: FeedItem): boolean {
		return Boolean(article.thumbnail) && !failedThumbnails.has(article.link);
	}

	function markThumbnailFailed(articleLink: string) {
		failedThumbnails = new Set([...failedThumbnails, articleLink]);
	}

	function getSourceInitials(source: string | null | undefined): string {
		return (source || '')
			.split(/\s+/)
			.filter(Boolean)
			.slice(0, 2)
			.map((part) => part[0]?.toUpperCase() ?? '')
			.join('');
	}

	// Helper function to merge articles with read statuses
	function mergeWithReadStatus(articles: FeedItem[]): FeedItem[] {
		return articles.map((article) => ({
			...article,
			is_read: readStatuses[article.link] || false
		}));
	}

	// Derived
	const categories = $derived((data.categories as Category[]) || []);

	// Use search results if in search mode, otherwise use original categories
	const displayCategories = $derived(isSearchMode ? searchResults : categories);

	// Use paginated articles if available, otherwise fall back to category-grouped data
	const baseFilteredArticles = $derived.by(() => {
		const articles =
			allArticles.length > 0
				? selectedCategory === 'all'
					? allArticles
					: allArticles.filter((article) => article.category === selectedCategory)
				: selectedCategory === 'all'
					? displayCategories.flatMap((cat) => cat.feed_items)
					: displayCategories.find((cat) => cat.category === selectedCategory)?.feed_items || [];

		return mergeWithReadStatus(articles);
	});

	$effect(() => {
		$page.url.search;

		const selectionChanged = applySelectionFromUrl();
		if (hasInitiallyLoaded && selectionChanged) {
			loadInitialArticles();
		}
	});

	// Filter out read articles if hideReadArticles is enabled
	const filteredArticles = $derived(
		hideReadArticles
			? baseFilteredArticles.filter((article) => !article.is_read)
			: baseFilteredArticles
	);

	// Total search result count (only relevant when searching)
	const searchResultCount = $derived(
		isSearchMode ? searchResults.flatMap((cat) => cat.feed_items).length : 0
	);

	// Functions
	async function loadArticleContent(url: string) {
		isLoadingContent = true;
		articleContent = '';
		try {
			const response = await fetch(`/api/article-full-text?url=${encodeURIComponent(url)}`);
			if (!response.ok) {
				throw new Error('Failed to load article');
			}
			const data = await response.json();
			articleContent = data.content || 'No content available';
		} catch (error) {
			articleContent = '<p class="text-destructive">Failed to load article content</p>';
			toast.error('Failed to load article content');
		} finally {
			isLoadingContent = false;
		}
	}

	function openArticleModal(article: FeedItem) {
		selectedArticle = article;
		modalOpen = true;
		loadArticleContent(article.link);
		// Mark as read when viewing
		markAsRead([article.link]);
	}

	function handleCategorySelect(category: string) {
		goto(buildFeedsUrl(category, null), { keepFocus: true, noScroll: true });
	}

	function handleFeedSelect(feedUrl: string, feedName: string) {
		selectedFeedName = feedName;
		goto(buildFeedsUrl('all', feedUrl), { keepFocus: true, noScroll: true });
	}

	async function handleConfigChanged() {
		await invalidateAll();
	}

	async function performSearch(query: string) {
		if (!query.trim()) {
			// Clear search - reload initial articles
			isSearchMode = false;
			searchResults = [];
			await loadInitialArticles();
			return;
		}

		// Reload with search query
		await loadInitialArticles();
	}

	function handleSearchInput(event: Event) {
		const target = event.target as HTMLInputElement;
		searchQuery = target.value;

		// Debounce search
		if (searchTimeout) {
			clearTimeout(searchTimeout);
		}

		searchTimeout = setTimeout(() => {
			performSearch(searchQuery);
		}, 300);
	}

	async function clearSearch() {
		searchQuery = '';
		isSearchMode = false;
		searchResults = [];
		await loadInitialArticles();
	}

	async function toggleStarredView() {
		isStarredViewActive = !isStarredViewActive;
		await loadInitialArticles();
	}

	async function toggleHideReadArticles() {
		hideReadArticles = !hideReadArticles;
	}

	async function toggleViewType() {
		viewType = viewType === 'standard' ? 'ai' : 'standard';
		await loadInitialArticles();
	}

	async function loadInitialArticles() {
		// Reset pagination state
		currentOffset = 0;
		allArticles = [];
		hasMore = true;

		const categoryParam =
			selectedCategory !== 'all' ? `&category=${encodeURIComponent(selectedCategory)}` : '';
		const feedParam = selectedFeedUrl ? `&feed_url=${encodeURIComponent(selectedFeedUrl)}` : '';
		const searchParam = searchQuery.trim() ? `&q=${encodeURIComponent(searchQuery)}` : '';
		const starredParam = isStarredViewActive ? '&starred_only=true' : '';
		const viewParam = `&view=${viewType}`;

		try {
			const response = await fetch(
				`/api/feeds?limit=${INITIAL_LOAD}&offset=0${categoryParam}${feedParam}${searchParam}${starredParam}${viewParam}`
			);
			if (!response.ok) throw new Error('Failed to fetch feeds');

			const data = await response.json();

			// Check if response is paginated format
			if (data.articles && Array.isArray(data.articles)) {
				allArticles = data.articles;
				totalArticles = data.total;
				hasMore = data.has_more;
				currentOffset = INITIAL_LOAD;
				console.log('[LazyLoad] Initial load:', {
					loaded: data.articles.length,
					total: data.total,
					hasMore: data.has_more,
					currentOffset: INITIAL_LOAD
				});
				// Fetch read statuses for loaded articles
				await fetchReadStatuses(data.articles);
			} else {
				// Fallback to old format (shouldn't happen with limit param)
				console.warn('Unexpected response format');
			}
		} catch (error) {
			console.error('Error loading articles:', error);
			toast.error('Failed to load articles');
		}
	}

	async function loadMoreArticles() {
		console.log(
			'[LazyLoad] loadMoreArticles called. isLoadingMore:',
			isLoadingMore,
			'hasMore:',
			hasMore
		);
		if (isLoadingMore || !hasMore) {
			console.log('[LazyLoad] Skipping load - already loading or no more articles');
			return;
		}

		isLoadingMore = true;

		const categoryParam =
			selectedCategory !== 'all' ? `&category=${encodeURIComponent(selectedCategory)}` : '';
		const feedParam = selectedFeedUrl ? `&feed_url=${encodeURIComponent(selectedFeedUrl)}` : '';
		const searchParam = searchQuery.trim() ? `&q=${encodeURIComponent(searchQuery)}` : '';
		const starredParam = isStarredViewActive ? '&starred_only=true' : '';
		const viewParam = `&view=${viewType}`;

		try {
			const response = await fetch(
				`/api/feeds?limit=${LOAD_MORE_SIZE}&offset=${currentOffset}${categoryParam}${feedParam}${searchParam}${starredParam}${viewParam}`
			);
			if (!response.ok) throw new Error('Failed to fetch more articles');

			const data = await response.json();

			if (data.articles && Array.isArray(data.articles)) {
				// Fetch read statuses for new articles
				await fetchReadStatuses(data.articles);
				allArticles = [...allArticles, ...data.articles];
				hasMore = data.has_more;
				currentOffset += data.articles.length;
				console.log('[LazyLoad] Loaded more articles:', {
					newArticles: data.articles.length,
					totalLoaded: allArticles.length,
					total: data.total,
					hasMore: data.has_more,
					currentOffset: currentOffset
				});
			}
		} catch (error) {
			console.error('Error loading more articles:', error);
			toast.error('Failed to load more articles');
		} finally {
			isLoadingMore = false;
		}
	}

	async function fetchFeedsData() {
		const categoryParam =
			selectedCategory !== 'all' ? `category=${encodeURIComponent(selectedCategory)}` : '';
		const searchParam = searchQuery.trim() ? `q=${encodeURIComponent(searchQuery)}` : '';
		const starredParam = isStarredViewActive ? 'starred_only=true' : '';
		const viewParam = `view=${viewType}`;

		const params = [categoryParam, searchParam, starredParam, viewParam].filter((p) => p).join('&');

		try {
			const response = await fetch(`/api/feeds?${params}`);
			if (!response.ok) throw new Error('Failed to fetch feeds');

			const results = await response.json();

			if (searchQuery.trim() || isStarredViewActive) {
				isSearchMode = true;
				searchResults = results;
			} else {
				isSearchMode = false;
				await invalidateAll();
			}
		} catch (error) {
			console.error('Error fetching feeds:', error);
			toast.error('Failed to load feeds');
		}
	}

	async function toggleArticleStar(article: FeedItem, event?: Event) {
		if (event) {
			event.stopPropagation();
			event.preventDefault();
		}

		// Optimistic update
		const previousStarred = article.starred;
		article.starred = !article.starred;

		try {
			const response = await fetch('/api/article/star', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					link: article.link,
					starred: article.starred
				})
			});

			if (!response.ok) {
				throw new Error('Failed to update starred status');
			}

			toast.success(article.starred ? 'Article starred!' : 'Article unstarred');

			// Mark as read when starring
			await markAsRead([article.link]);

			// If in starred view and article was unstarred, refresh to remove it
			if (isStarredViewActive && !article.starred) {
				await fetchFeedsData();
			}
		} catch (error) {
			// Revert on error
			article.starred = previousStarred;
			console.error('Error toggling star:', error);
			toast.error('Failed to update starred status');
		}
	}

	async function fetchReadStatuses(articles: FeedItem[]) {
		if (articles.length === 0) return;

		const links = articles.map((a) => a.link);

		try {
			const response = await fetch('/api/articles/statuses', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ links })
			});

			if (!response.ok) {
				throw new Error('Failed to fetch read statuses');
			}

			const statuses = await response.json();

			// Update readStatuses state for reactivity
			readStatuses = { ...readStatuses, ...statuses };
		} catch (error) {
			console.error('Error fetching read statuses:', error);
		}
	}

	async function markAsRead(links: string[]) {
		if (links.length === 0) return;

		try {
			// Optimistically update readStatuses state
			const newStatuses = { ...readStatuses };
			links.forEach((link) => {
				newStatuses[link] = true;
			});
			readStatuses = newStatuses;

			const response = await fetch('/api/articles/mark-as-read', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ links })
			});

			if (!response.ok) {
				throw new Error('Failed to mark articles as read');
			}
		} catch (error) {
			console.error('Error marking articles as read:', error);
			// Could revert optimistic update here if needed
		}
	}

	// Navigate to next article in column view
	function navigateNext() {
		if (viewMode !== 'column' || filteredArticles.length === 0) return;

		// Mark current article as read
		if (filteredArticles[selectedColumnIndex]) {
			markAsRead([filteredArticles[selectedColumnIndex].link]);
		}

		const isLastArticle = selectedColumnIndex >= filteredArticles.length - 1;

		// When hideReadArticles is enabled, the current article is removed,
		// and the next article takes its place at the same index.
		if (hideReadArticles) {
			if (isLastArticle) {
				selectedColumnIndex = 0; // Loop to top
			}
			// Otherwise, stay at the same index.
		} else {
			// Normal navigation: move to the next article or loop
			selectedColumnIndex = isLastArticle ? 0 : selectedColumnIndex + 1;
		}

		// Load the article at the new index
		setTimeout(() => {
			if (filteredArticles[selectedColumnIndex]) {
				loadArticleContent(filteredArticles[selectedColumnIndex].link);
			}
		}, 50);
	}

	// Navigate to previous article in column view
	function navigatePrevious() {
		if (viewMode !== 'column' || filteredArticles.length === 0) return;

		// Mark current article as read
		if (filteredArticles[selectedColumnIndex]) {
			markAsRead([filteredArticles[selectedColumnIndex].link]);
		}

		const isFirstArticle = selectedColumnIndex === 0;

		// Move to the previous article or loop to the end
		selectedColumnIndex = isFirstArticle ? filteredArticles.length - 1 : selectedColumnIndex - 1;

		// Load the article at the new index
		setTimeout(() => {
			if (filteredArticles[selectedColumnIndex]) {
				loadArticleContent(filteredArticles[selectedColumnIndex].link);
			}
		}, 50);
	}

	// Enhanced keyboard shortcuts for all essential functions
	function handleKeydown(event: KeyboardEvent) {
		// Don't trigger shortcuts when typing in input fields
		const target = event.target as HTMLElement;
		if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
			// Allow Escape to blur input fields
			if (event.key === 'Escape') {
				target.blur();
			}
			return;
		}

		// Column view navigation (Arrow keys)
		if (viewMode === 'column' && filteredArticles.length > 0) {
			if (event.key === 'ArrowDown' || event.key === 'j') {
				event.preventDefault();
				navigateNext();
				return;
			} else if (event.key === 'ArrowUp' || event.key === 'k') {
				event.preventDefault();
				navigatePrevious();
				return;
			}
		}

		// Global shortcuts
		switch (event.key) {
			case '/':
				// Focus search input
				event.preventDefault();
				searchInputRef?.focus();
				break;

			case 's':
				// Star current article
				event.preventDefault();
				if (viewMode === 'column' && filteredArticles[selectedColumnIndex]) {
					toggleArticleStar(filteredArticles[selectedColumnIndex]);
				}
				break;

			case 'o':
				// Open current article in new tab
				event.preventDefault();
				if (viewMode === 'column' && filteredArticles[selectedColumnIndex]) {
					window.open(filteredArticles[selectedColumnIndex].link, '_blank', 'noopener,noreferrer');
				}
				break;

			case 'r':
				// Mark current article as read
				event.preventDefault();
				if (viewMode === 'column' && filteredArticles[selectedColumnIndex]) {
					markAsRead([filteredArticles[selectedColumnIndex].link]);
				}
				break;

			case '1':
				// Switch to card view
				event.preventDefault();
				viewMode = 'card';
				break;

			case '2':
				// Switch to headline view
				event.preventDefault();
				viewMode = 'headline';
				break;

			case '3':
				// Switch to column view
				event.preventDefault();
				viewMode = 'column';
				break;

			case 'a':
				// Toggle AI filter view
				event.preventDefault();
				toggleViewType();
				break;

			case 'f':
				// Toggle starred/favorites view
				event.preventDefault();
				toggleStarredView();
				break;

			case 'h':
				// Toggle hide read articles
				event.preventDefault();
				toggleHideReadArticles();
				break;

			case '?':
				// Show keyboard shortcuts help
				event.preventDefault();
				showShortcutsModal = !showShortcutsModal;
				break;
		}
	}

	// Summarize article using AI
	async function summarizeArticle(article: FeedItem) {
		summaryArticle = article;
		summaryText = '';
		showSummaryModal = true;
		isLoadingSummary = true;

		try {
			const response = await fetch('/api/article/summarize', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ link: article.link })
			});

			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.error || 'Failed to generate summary');
			}

			const result = await response.json();
			summaryText = result.summary;
		} catch (error) {
			console.error('Error generating summary:', error);
			toast.error(error instanceof Error ? error.message : 'Failed to generate summary');
			showSummaryModal = false;
		} finally {
			isLoadingSummary = false;
		}
	}

	// Generate starred report for current category
	async function generateStarredReport() {
		if (selectedCategory === 'all') {
			toast.error('Please select a specific category to generate a report');
			return;
		}

		isGeneratingReport = true;

		try {
			const response = await fetch(
				`/api/reports/generate/starred/${encodeURIComponent(selectedCategory)}`,
				{
					method: 'POST',
					headers: { 'Content-Type': 'application/json' }
				}
			);

			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.detail || 'Failed to generate report');
			}

			const result = await response.json();
			toast.success(`Report generated successfully! ${result.article_count} articles included.`);
		} catch (error) {
			console.error('Error generating report:', error);
			toast.error(error instanceof Error ? error.message : 'Failed to generate report');
		} finally {
			isGeneratingReport = false;
		}
	}

	// Track previous view mode to detect when switching to column view
	let previousViewMode = $state<ViewMode>('card');

	// Initialize column view only when first entering it
	$effect(() => {
		if (viewMode === 'column' && previousViewMode !== 'column' && filteredArticles.length > 0) {
			// First time entering column view
			selectedColumnIndex = 0;
			loadArticleContent(filteredArticles[0].link);
		}
		previousViewMode = viewMode;
	});

	// Handle index adjustment when articles change in column view
	$effect(() => {
		if (viewMode === 'column' && filteredArticles.length > 0) {
			// Validate current index is still in bounds
			if (selectedColumnIndex >= filteredArticles.length) {
				// Index out of bounds, adjust to last article
				selectedColumnIndex = Math.max(0, filteredArticles.length - 1);
				loadArticleContent(filteredArticles[selectedColumnIndex].link);
			} else if (selectedColumnIndex < 0) {
				// Reset to first article if index is negative
				selectedColumnIndex = 0;
				loadArticleContent(filteredArticles[0].link);
			}
			// Otherwise, keep the current index (article may have changed but index stays same)
		}
	});

	// Scroll selected article into view in column mode
	$effect(() => {
		if (viewMode === 'column' && filteredArticles.length > 0) {
			const el = document.getElementById(`article-column-${selectedColumnIndex}`);
			if (el) {
				el.scrollIntoView({
					behavior: 'smooth',
					block: 'nearest'
				});
			}
		}
	});

	// Fetch read statuses for initial server-loaded categories data
	let hasLoadedInitialStatuses = false;
	$effect(() => {
		if (!hasLoadedInitialStatuses && categories.length > 0) {
			hasLoadedInitialStatuses = true;
			const allCategoryArticles = categories.flatMap((cat) => cat.feed_items);
			if (allCategoryArticles.length > 0) {
				fetchReadStatuses(allCategoryArticles);
			}
		}
	});

	// Load initial articles on mount (run once)
	let hasInitiallyLoaded = false;
	$effect(() => {
		if (!hasInitiallyLoaded) {
			applySelectionFromUrl();
			hasInitiallyLoaded = true;
			loadInitialArticles();
		}
	});

	// Intersection Observer for lazy loading
	$effect(() => {
		// Re-run effect when articles are loaded or pagination state changes
		// Reference allArticles to make effect reactive to article loading
		const articlesLoaded = allArticles.length;
		const shouldLoad = hasMore && !isLoadingMore;

		// Skip if no articles loaded yet
		if (articlesLoaded === 0) {
			console.log('[LazyLoad] No articles loaded yet, skipping observer setup');
			return;
		}

		let observer: IntersectionObserver | null = null;

		// Wait a tick for DOM to update after articles are rendered
		const timeoutId = setTimeout(() => {
			// Find all load-more triggers and observe only the visible one based on viewMode
			const triggers = document.querySelectorAll('.load-more-trigger');
			console.log(
				'[LazyLoad] Setting up observer. Triggers found:',
				triggers.length,
				'hasMore:',
				hasMore,
				'isLoadingMore:',
				isLoadingMore,
				'articlesLoaded:',
				articlesLoaded
			);

			if (triggers.length === 0) {
				console.log('[LazyLoad] No triggers found, skipping observer setup');
				return;
			}

			observer = new IntersectionObserver(
				(entries) => {
					console.log('[LazyLoad] Observer triggered with', entries.length, 'entries');
					entries.forEach((entry) => {
						console.log('[LazyLoad] Entry:', {
							isIntersecting: entry.isIntersecting,
							target: entry.target.className,
							hasMore,
							isLoadingMore
						});
						// Check current state values, not captured closure
						if (entry.isIntersecting && hasMore && !isLoadingMore) {
							console.log(
								'[LazyLoad] Trigger intersected, loading more articles. hasMore:',
								hasMore,
								'isLoadingMore:',
								isLoadingMore
							);
							loadMoreArticles();
						}
					});
				},
				{
					root: null,
					rootMargin: '200px', // Start loading 200px before reaching the trigger
					threshold: 0.1
				}
			);

			console.log('[LazyLoad] Observing', triggers.length, 'triggers');
			// Observe all triggers (only the visible one will actually trigger)
			triggers.forEach((trigger) => observer!.observe(trigger));
		}, 100);

		return () => {
			clearTimeout(timeoutId);
			if (observer) {
				console.log('[LazyLoad] Disconnecting observer');
				observer.disconnect();
			}
		};
	});

	// Check for new articles since last timestamp
	async function checkForUpdates() {
		try {
			console.log('[Updates] Checking for updates since:', lastCheckTimestamp);
			const response = await fetch(
				`/api/articles/updates?since=${encodeURIComponent(lastCheckTimestamp)}`
			);
			if (!response.ok) {
				console.error('[Updates] Response not OK:', response.status);
				return;
			}

			const data = await response.json();
			console.log('[Updates] Response data:', data);

			if (data.total > 0) {
				newArticlesCount = data.total;
				newArticlesByCategory = data.by_category;

				// Show toast notification
				const categoryText = Object.entries(data.by_category)
					.map(([cat, count]) => `${cat}: ${count}`)
					.join(', ');

				console.log('[Updates] New articles found:', data.total);
				toast.info(
					`${data.total} new article${data.total > 1 ? 's' : ''} available${categoryText ? ` (${categoryText})` : ''}`,
					{
						duration: 5000,
						action: {
							label: 'Refresh',
							onClick: () => refreshToShowNewArticles()
						}
					}
				);
			}

			// Update timestamp for next check
			lastCheckTimestamp = data.timestamp;
			console.log('[Updates] Next check will be since:', lastCheckTimestamp);
		} catch (error) {
			console.error('[Updates] Error checking for updates:', error);
		}
	}

	// Refresh page to show new articles
	async function refreshToShowNewArticles() {
		newArticlesCount = 0;
		newArticlesByCategory = {};
		await loadInitialArticles();
		toast.success('Feed refreshed!');
	}

	function handleFeedScroll() {
		showScrollToTop = (scrollContainer?.scrollTop ?? 0) > 600;
	}

	function scrollToTop() {
		scrollContainer?.scrollTo({ top: 0, behavior: 'smooth' });
	}

	// Start polling for updates every 30 seconds
	onMount(async () => {
		// Load settings and set default view mode
		await settings.load();
		unsubscribe = settings.subscribe((s) => {
			timezone = s.timezone;
			if (s.default_view && viewMode === 'card') {
				// Only set default view on initial load (when viewMode is still at default 'card')
				viewMode = s.default_view;
			}
		});

		// Initial timestamp
		lastCheckTimestamp = new Date().toISOString();
		console.log('[Updates] Polling started. Initial timestamp:', lastCheckTimestamp);

		// Poll every 30 seconds
		updateCheckInterval = setInterval(() => {
			console.log('[Updates] Polling interval triggered');
			checkForUpdates();
		}, 30000);
	});

	// Also cleanup on destroy
	onDestroy(() => {
		if (unsubscribe) {
			unsubscribe();
		}
		if (updateCheckInterval) {
			clearInterval(updateCheckInterval);
		}
	});
</script>

<svelte:window onkeydown={handleKeydown} />

<Sidebar.Provider class="h-full">
	<div class="flex h-full w-full">
		<!-- Sidebar -->
		<FeedSidebar
			{selectedCategory}
			{selectedFeedUrl}
			onCategorySelect={handleCategorySelect}
			onFeedSelect={handleFeedSelect}
			onconfigchanged={handleConfigChanged}
		/>

		<!-- Main Content -->
		<Sidebar.Inset class="h-full">
			<div
				bind:this={scrollContainer}
				class="h-full w-full overflow-auto"
				onscroll={handleFeedScroll}
			>
				<div class="px-4 py-4 sm:px-6 sm:py-6 md:px-8 md:py-8">
					<!-- Header -->
					<div class="mb-6 flex flex-col gap-3 md:mb-8 md:gap-4">
						<div
							class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between md:gap-4"
						>
							<div class="flex min-w-0 items-center gap-2">
								<Sidebar.Trigger class="shrink-0" />
								<h1 class="truncate text-xl font-bold sm:text-2xl">
									{selectedFeedUrl
										? (selectedFeedName ?? getFeedDisplayName(selectedFeedUrl) ?? 'Selected Feed')
										: selectedCategory === 'all'
											? 'All Feeds'
											: selectedCategory}
								</h1>
								{#if isSearchMode && searchQuery}
									<Badge variant="outline" class="shrink-0 text-xs">
										{searchResultCount} result{searchResultCount !== 1 ? 's' : ''}
									</Badge>
								{/if}
							</div>

							<div class="flex w-full flex-wrap items-center gap-2 sm:gap-3 md:w-auto md:shrink-0">
								<!-- New Articles Indicator -->
								{#if newArticlesCount > 0}
									<Button
										variant="outline"
										size="sm"
										onclick={refreshToShowNewArticles}
										class="flex w-full items-center gap-2 border-primary/30 bg-primary/10 hover:bg-primary/20 sm:w-auto"
									>
										<Bell class="size-4" />
										<span class="font-medium">{newArticlesCount} new</span>
									</Button>
								{/if}

								<!-- Search Input -->
								<div class="relative order-first w-full md:order-none md:w-64">
									<Search
										class="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
									/>
									<Input
										type="text"
										placeholder="Search articles..."
										value={searchQuery}
										oninput={handleSearchInput}
										class="pr-9 pl-9"
										disabled={isSearching}
										bind:ref={searchInputRef}
									/>
									{#if searchQuery}
										<button
											onclick={clearSearch}
											class="absolute top-1/2 right-3 -translate-y-1/2 text-muted-foreground hover:text-foreground"
											aria-label="Clear search"
										>
											<X class="size-4" />
										</button>
									{/if}
								</div>

								<!-- Generate Report Button (only show for specific category) -->
								{#if selectedCategory !== 'all'}
									<Button
										variant="outline"
										size="sm"
										onclick={generateStarredReport}
										disabled={isGeneratingReport}
										aria-label="Generate starred report"
										class="w-full sm:w-auto"
									>
										<FileText class="mr-2 size-4" />
										{isGeneratingReport ? 'Generating...' : 'Generate Report'}
									</Button>
								{/if}

								<!-- Starred View Toggle -->
								<Button
									variant={isStarredViewActive ? 'default' : 'outline'}
									size="icon"
									onclick={toggleStarredView}
									aria-label="Starred articles"
									class={isStarredViewActive ? 'bg-yellow-500 hover:bg-yellow-600' : ''}
								>
									<Star class="size-4" fill={isStarredViewActive ? 'currentColor' : 'none'} />
								</Button>

								<!-- Hide/Show Read Toggle -->
								<Button
									variant={hideReadArticles ? 'default' : 'outline'}
									size="icon"
									onclick={toggleHideReadArticles}
									aria-label={hideReadArticles ? 'Show read articles' : 'Hide read articles'}
									title={hideReadArticles ? 'Showing unread only' : 'Show all articles'}
								>
									{#if hideReadArticles}
										<CheckCircle class="size-4" />
									{:else}
										<Circle class="size-4" />
									{/if}
								</Button>

								<!-- AI View Toggle with Count -->
								<div class="flex items-center gap-2">
									<Button
										variant={viewType === 'ai' ? 'default' : 'outline'}
										size="icon"
										onclick={toggleViewType}
										aria-label={viewType === 'ai'
											? 'Switch to standard view'
											: 'Switch to AI filtered view'}
										title={viewType === 'ai' ? 'AI Filtered View' : 'Standard View'}
										class={viewType === 'ai' ? 'bg-purple-500 hover:bg-purple-600' : ''}
									>
										<Sparkles class="size-4" />
									</Button>
									{#if viewType === 'ai' && totalArticles > 0}
										<Badge variant="secondary" class="font-mono text-xs">
											{filteredArticles.length}/{totalArticles}
										</Badge>
									{/if}
								</div>

								<!-- View Mode Toggle -->
								<div class="ml-auto flex gap-2 sm:ml-0">
									<Button
										variant={viewMode === 'card' ? 'default' : 'outline'}
										size="icon"
										onclick={() => (viewMode = 'card')}
										aria-label="Card view"
									>
										<LayoutGrid class="size-4" />
									</Button>
									<Button
										variant={viewMode === 'headline' ? 'default' : 'outline'}
										size="icon"
										onclick={() => (viewMode = 'headline')}
										aria-label="Headline view"
									>
										<List class="size-4" />
									</Button>
									<Button
										variant={viewMode === 'column' ? 'default' : 'outline'}
										size="icon"
										onclick={() => (viewMode = 'column')}
										aria-label="Column view"
									>
										<Columns2 class="size-4" />
									</Button>
								</div>
							</div>
						</div>
						<Separator />
					</div>

					<!-- Content -->
					{#if filteredArticles.length === 0}
						<div class="flex flex-col items-center justify-center py-16 text-center">
							{#if isStarredViewActive}
								<Star class="mb-4 size-16 text-muted-foreground" />
								<p class="text-lg text-muted-foreground">No starred articles</p>
								<p class="text-sm text-muted-foreground">
									{selectedCategory === 'all'
										? 'Star some articles to see them here'
										: `No starred articles in ${selectedCategory}`}
								</p>
								<Button variant="outline" class="mt-4" onclick={toggleStarredView}>
									Show All Articles
								</Button>
							{:else if isSearchMode}
								<p class="text-lg text-muted-foreground">No results found for "{searchQuery}"</p>
								<p class="text-sm text-muted-foreground">
									Try a different search term or clear the search
								</p>
								<Button variant="outline" class="mt-4" onclick={clearSearch}>Clear Search</Button>
							{:else}
								<p class="text-lg text-muted-foreground">No articles found</p>
								<p class="text-sm text-muted-foreground">Try selecting a different category</p>
							{/if}
						</div>
					{:else if viewMode === 'card'}
						<!-- Card View -->
						<div
							class="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-6 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5"
						>
							{#each filteredArticles as article}
								<Card
									class="group flex flex-col overflow-hidden p-4 transition-all hover:shadow-lg sm:p-6 {article.is_read
										? 'opacity-60'
										: ''}"
								>
									<div class="flex flex-grow flex-col gap-4">
										{#if hasThumbnail(article)}
											<div
												class="relative -mx-4 -mt-4 overflow-hidden rounded-t-xl sm:-mx-6 sm:-mt-6"
											>
												<img
													src={article.thumbnail}
													alt={article.title}
													class="h-48 w-full object-cover transition-transform duration-300 group-hover:scale-105"
													onerror={(e) => {
														markThumbnailFailed(article.link);
													}}
												/>
											</div>
										{:else}
											<div
												class="relative -mx-4 -mt-4 overflow-hidden rounded-t-xl border-b bg-gradient-to-br from-muted/80 via-muted/45 to-background sm:-mx-6 sm:-mt-6"
											>
												<div class="flex h-48 flex-col justify-between p-4">
													<div
														class="flex items-center justify-between gap-3 text-muted-foreground/80"
													>
														<span
															class="truncate rounded-full border border-border/70 bg-background/70 px-2.5 py-1 text-[10px] font-semibold tracking-[0.22em] uppercase"
														>
															{article.source}
														</span>
														<FileText class="size-4 shrink-0" />
													</div>
													<div class="flex items-end justify-between gap-4">
														<div>
															<div class="text-3xl font-semibold tracking-tight text-foreground/75">
																{getSourceInitials(article.source) || 'NS'}
															</div>
															<div
																class="mt-1 text-xs tracking-[0.25em] text-muted-foreground uppercase"
															>
																Article
															</div>
														</div>
														<div
															class="rounded-full border border-border/70 bg-background/80 p-2 shadow-sm"
														>
															<FileText class="size-4 text-muted-foreground" />
														</div>
													</div>
												</div>
											</div>
										{/if}
										<div class="flex flex-grow flex-col justify-between gap-3">
											<div>
												<div class="flex items-center gap-2">
													<Badge variant="secondary">{article.source}</Badge>
													<span class="text-xs text-muted-foreground"
														>{formatPublishedDate(article.published_datetime, timezone)}</span
													>
												</div>
												<h3 class="mt-2 line-clamp-2 text-lg leading-tight">{article.title}</h3>
												{#if article.description}
													<p class="mt-1 line-clamp-3 text-sm text-muted-foreground">
														{article.description}
													</p>
												{/if}
											</div>
											<div class="flex flex-wrap justify-end gap-2">
												<Button
													variant="outline"
													size="icon-sm"
													onclick={(e) => toggleArticleStar(article, e)}
													class={article.starred ? 'text-yellow-500 hover:text-yellow-600' : ''}
													title="Star article"
												>
													<Star class="size-4" fill={article.starred ? 'currentColor' : 'none'} />
												</Button>
												<Button
													variant="outline"
													size="icon-sm"
													onclick={() => summarizeArticle(article)}
													title="Summarize with AI"
												>
													<Sparkles class="size-4" />
												</Button>
												<Button
													variant="outline"
													size="icon-sm"
													onclick={() => openArticleModal(article)}
													title="Read article"
												>
													<Eye class="size-4" />
												</Button>
												<Button
													variant="outline"
													size="icon-sm"
													href={article.link}
													target="_blank"
													rel="noopener noreferrer"
													title="Open in new tab"
												>
													<ExternalLink class="size-4" />
												</Button>
											</div>
										</div>
									</div>
								</Card>
							{/each}
						</div>

						<!-- Load More Trigger for Card View -->
						<div class="load-more-trigger">
							{#if hasMore || isLoadingMore}
								<div class="flex justify-center py-8">
									{#if isLoadingMore}
										<div class="flex items-center gap-2 text-muted-foreground">
											<div
												class="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent"
											></div>
											<span>Loading more articles...</span>
										</div>
									{:else}
										<span class="text-sm text-muted-foreground">Scroll for more</span>
									{/if}
								</div>
							{:else if allArticles.length > 0}
								<div class="flex justify-center py-8">
									<span class="text-sm text-muted-foreground">No more articles</span>
								</div>
							{/if}
						</div>
					{:else if viewMode === 'headline'}
						<!-- Headline View -->
						<div class="mx-auto">
							<ul class="grid grid-cols-1 gap-4 md:grid-cols-2">
								{#each filteredArticles as article}
									<li
										class="group flex items-center gap-4 rounded-lg border p-4 transition-all hover:bg-muted {article.is_read
											? 'opacity-60'
											: ''}"
									>
										<div class="flex min-w-0 flex-1 flex-col gap-1">
											<h3 class="leading-snug">{article.title}</h3>
											<div class="flex items-center gap-2 text-xs text-muted-foreground">
												<span>{article.source}</span>
												<span>&bull;</span>
												<span>{formatPublishedDate(article.published_datetime, timezone)}</span>
											</div>
										</div>
										<div class="flex shrink-0 flex-wrap gap-2">
											<Button
												variant="ghost"
												size="icon-sm"
												onclick={(e) => toggleArticleStar(article, e)}
												class={article.starred ? 'text-yellow-500 hover:text-yellow-600' : ''}
												title="Star article"
											>
												<Star class="size-4" fill={article.starred ? 'currentColor' : 'none'} />
											</Button>
											<Button
												variant="ghost"
												size="icon-sm"
												onclick={() => summarizeArticle(article)}
												title="Summarize with AI"
											>
												<Sparkles class="size-4" />
											</Button>
											<Button
												variant="ghost"
												size="icon-sm"
												onclick={() => openArticleModal(article)}
												title="Read article"
											>
												<Eye class="size-4" />
											</Button>
											<Button
												variant="ghost"
												size="icon-sm"
												href={article.link}
												target="_blank"
												rel="noopener noreferrer"
												title="Open in new tab"
											>
												<ExternalLink class="size-4" />
											</Button>
										</div>
									</li>
								{/each}
							</ul>
						</div>

						<!-- Load More Trigger for Headline View -->
						<div class="load-more-trigger">
							{#if hasMore || isLoadingMore}
								<div class="flex justify-center py-8">
									{#if isLoadingMore}
										<div class="flex items-center gap-2 text-muted-foreground">
											<div
												class="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent"
											></div>
											<span>Loading more articles...</span>
										</div>
									{:else}
										<span class="text-sm text-muted-foreground">Scroll for more</span>
									{/if}
								</div>
							{:else if allArticles.length > 0}
								<div class="flex justify-center py-8">
									<span class="text-sm text-muted-foreground">No more articles</span>
								</div>
							{/if}
						</div>
					{:else if viewMode === 'column'}
						<!-- Column View -->
						<div class="flex flex-col gap-6 lg:grid lg:grid-cols-2">
							<!-- Article List -->
							<div class="flex flex-col gap-2">
								{#each filteredArticles as article, index}
									<Card
										id={`article-column-${index}`}
										class="group cursor-pointer transition-all {selectedColumnIndex === index
											? 'ring-2 ring-primary lg:ring-2'
											: 'hover:shadow-md'} {article.is_read ? 'opacity-60' : ''}"
										onclick={() => {
											// On mobile, open article in modal instead of side-by-side
											if (window.innerWidth < 1024) {
												openArticleModal(article);
												return;
											}

											// Mark previous article as read when switching
											if (selectedColumnIndex !== index && filteredArticles[selectedColumnIndex]) {
												const previousArticleLink = filteredArticles[selectedColumnIndex].link;
												markAsRead([previousArticleLink]);

												// If hideReadArticles is enabled and we marked an article before this one,
												// the index will shift down by 1
												if (hideReadArticles && selectedColumnIndex < index) {
													selectedColumnIndex = index - 1;
												} else {
													selectedColumnIndex = index;
												}
											} else {
												selectedColumnIndex = index;
											}
											loadArticleContent(article.link);
										}}
									>
										<div class="flex items-start gap-4 px-6 py-4">
											{#if hasThumbnail(article)}
												<img
													src={article.thumbnail}
													alt={article.title}
													class="h-12 w-16 shrink-0 rounded-md object-cover sm:h-16 sm:w-24"
													onerror={() => {
														markThumbnailFailed(article.link);
													}}
												/>
											{:else}
												<div
													class="flex h-12 w-16 shrink-0 items-center justify-center rounded-md border border-border/60 bg-gradient-to-br from-muted/80 via-muted/45 to-background sm:h-16 sm:w-24"
												>
													<div class="flex flex-col items-center gap-1 text-muted-foreground/85">
														<div class="text-[10px] font-semibold tracking-[0.18em] uppercase">
															{getSourceInitials(article.source) || 'NS'}
														</div>
														<FileText class="size-3.5 sm:size-4" />
													</div>
												</div>
											{/if}
											<div class="flex min-w-0 flex-1 flex-col gap-2">
												<div class="flex items-center gap-2">
													<Badge variant="secondary">{article.source}</Badge>
													<span class="text-xs text-muted-foreground"
														>{formatPublishedDate(article.published_datetime, timezone)}</span
													>
												</div>
												<h3 class="line-clamp-2 text-base leading-snug">{article.title}</h3>
											</div>
											<Button
												variant="ghost"
												size="icon-sm"
												onclick={(e) => toggleArticleStar(article, e)}
												class={article.starred ? 'text-yellow-500 hover:text-yellow-600' : ''}
											>
												<Star class="size-4" fill={article.starred ? 'currentColor' : 'none'} />
											</Button>
										</div>
									</Card>
								{/each}

								<!-- Load More Trigger for Column View -->
								<div class="load-more-trigger">
									{#if hasMore || isLoadingMore}
										<div class="flex justify-center py-4">
											{#if isLoadingMore}
												<div class="flex items-center gap-2 text-muted-foreground">
													<div
														class="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent"
													></div>
													<span>Loading more...</span>
												</div>
											{:else}
												<span class="text-sm text-muted-foreground">Scroll for more</span>
											{/if}
										</div>
									{:else if allArticles.length > 0}
										<div class="flex justify-center py-4">
											<span class="text-sm text-muted-foreground">No more articles</span>
										</div>
									{/if}
								</div>
							</div>

							<!-- Article Content -->
							<div class="sticky top-4 hidden h-fit lg:block">
								<Card class="max-h-[80vh] overflow-auto">
									{#if isLoadingContent}
										<div class="flex items-center justify-center py-16">
											<p class="text-muted-foreground">Loading article...</p>
										</div>
									{:else if filteredArticles[selectedColumnIndex]}
										<div class="flex flex-col gap-4 px-6 py-4">
											<div class="flex items-start justify-between gap-4">
												<div class="flex-1">
													<h2 class="text-xl leading-tight font-bold">
														{filteredArticles[selectedColumnIndex].title}
													</h2>
													<div class="mt-2 flex items-center gap-2">
														<Badge variant="secondary"
															>{filteredArticles[selectedColumnIndex].source}</Badge
														>
														<span class="text-xs text-muted-foreground"
															>{formatPublishedDate(
																filteredArticles[selectedColumnIndex].published_datetime,
																timezone
															)}</span
														>
													</div>
												</div>
												<div class="flex shrink-0 flex-wrap gap-2">
													<Button
														variant="outline"
														size="icon-sm"
														onclick={(e) =>
															toggleArticleStar(filteredArticles[selectedColumnIndex], e)}
														class={filteredArticles[selectedColumnIndex].starred
															? 'text-yellow-500 hover:text-yellow-600'
															: ''}
														title="Star article"
													>
														<Star
															class="size-4"
															fill={filteredArticles[selectedColumnIndex].starred
																? 'currentColor'
																: 'none'}
														/>
													</Button>
													<Button
														variant="outline"
														size="icon-sm"
														onclick={() => summarizeArticle(filteredArticles[selectedColumnIndex])}
														title="Summarize with AI"
													>
														<Sparkles class="size-4" />
													</Button>
													<Button
														variant="outline"
														size="icon-sm"
														onclick={() =>
															copyToClipboard(
																filteredArticles[selectedColumnIndex].link,
																'Link copied to clipboard!'
															)}
														title="Copy link"
													>
														<Copy class="size-4" />
													</Button>
													<Button
														variant="outline"
														size="icon-sm"
														href={filteredArticles[selectedColumnIndex].link}
														target="_blank"
														rel="noopener noreferrer"
														title="Open in new tab"
													>
														<ExternalLink class="size-4" />
													</Button>
												</div>
											</div>
											<Separator />
											<YoutubeEmbed htmlContent={articleContent} />
										</div>
									{/if}
								</Card>

								<!-- Navigation Controls -->
								{#if filteredArticles.length > 0}
									<div
										class="mt-4 flex items-center justify-between rounded-lg border bg-card p-4 text-card-foreground shadow-sm"
									>
										<div class="text-sm text-muted-foreground">
											Article {selectedColumnIndex + 1} of {filteredArticles.length}
										</div>
										<div class="flex gap-2">
											<Button
												variant="outline"
												size="sm"
												onclick={navigatePrevious}
												disabled={filteredArticles.length === 0}
												title="Previous article (↑ or k)"
											>
												<ChevronUp class="mr-1 size-4" />
												Previous
											</Button>
											<Button
												variant="outline"
												size="sm"
												onclick={navigateNext}
												disabled={filteredArticles.length === 0}
												title="Next article (↓ or j)"
											>
												Next
												<ChevronDown class="ml-1 size-4" />
											</Button>
										</div>
									</div>
								{/if}
							</div>
						</div>
					{/if}
				</div>
			</div>
		</Sidebar.Inset>
	</div>
</Sidebar.Provider>

<!-- Article Modal -->
{#if selectedArticle}
	<Dialog bind:open={modalOpen} title={selectedArticle.title}>
		<div class="flex flex-col gap-4">
			<div class="flex flex-col gap-3 sm:flex-row sm:items-center">
				<Badge variant="secondary">{selectedArticle.source}</Badge>
				<span class="text-xs text-muted-foreground"
					>{formatPublishedDate(selectedArticle.published_datetime, timezone)}</span
				>
				<div class="flex items-center gap-2 sm:ml-auto">
					<Button
						variant="outline"
						size="icon-sm"
						onclick={() => copyToClipboard(selectedArticle!.link, 'Link copied to clipboard!')}
						aria-label="Copy link"
						title="Copy link"
					>
						<Copy class="size-4" />
					</Button>
					<Button
						variant="outline"
						size="icon-sm"
						href={selectedArticle.link}
						target="_blank"
						rel="noopener noreferrer"
						aria-label="Open in new tab"
						title="Open in new tab"
					>
						<ExternalLink class="size-4" />
					</Button>
				</div>
			</div>
			{#if isLoadingContent}
				<div class="flex items-center justify-center py-8">
					<p class="text-muted-foreground">Loading article content...</p>
				</div>
			{:else}
				<div class="max-h-[60vh] overflow-auto sm:max-h-[70vh]">
					<YoutubeEmbed htmlContent={articleContent} />
				</div>
			{/if}
		</div>
	</Dialog>
{/if}

<!-- Keyboard Shortcuts Modal -->
<KeyboardShortcutsDialog bind:open={showShortcutsModal} />

<!-- Floating Help Button -->
<div class="fixed right-4 bottom-4 z-50 flex flex-col gap-2 sm:right-8 sm:bottom-8">
	{#if showScrollToTop}
		<Button
			variant="outline"
			size="icon"
			class="rounded-full shadow-lg"
			onclick={scrollToTop}
			aria-label="Scroll to top"
			title="Back to top"
		>
			<ChevronUp class="size-5" />
		</Button>
	{/if}
	<Button
		variant="outline"
		size="icon"
		class="rounded-full shadow-lg"
		onclick={() => (showShortcutsModal = true)}
		aria-label="Show keyboard shortcuts"
	>
		<HelpCircle class="size-5" />
	</Button>
</div>

<!-- Summary Modal -->
{#if summaryArticle}
	<Dialog bind:open={showSummaryModal} title="AI Summary">
		<div class="flex flex-col gap-4">
			<div class="flex flex-col gap-2">
				<h3 class="text-lg font-semibold">{summaryArticle.title}</h3>
				<div class="flex items-center gap-2">
					<Badge variant="secondary">{summaryArticle.source}</Badge>
					<span class="text-xs text-muted-foreground"
						>{formatPublishedDate(summaryArticle.published_datetime, timezone)}</span
					>
				</div>
			</div>

			<Separator />

			{#if isLoadingSummary}
				<div class="flex flex-col items-center justify-center gap-3 py-8">
					<div
						class="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"
					></div>
					<p class="text-sm text-muted-foreground">Generating summary with AI...</p>
				</div>
			{:else if summaryText}
				<div class="space-y-3">
					<div class="flex items-center gap-2 text-sm text-muted-foreground">
						<Sparkles class="h-4 w-4" />
						<span>AI-generated summary</span>
					</div>
					<div class="rounded-lg bg-muted p-4 text-sm leading-relaxed">
						{summaryText}
					</div>
				</div>

				<div class="flex flex-col gap-2 pt-2 sm:flex-row sm:justify-end">
					<Button
						variant="outline"
						size="sm"
						onclick={() => {
							if (summaryArticle) {
								openArticleModal(summaryArticle);
							}
						}}
						class="w-full sm:w-auto"
					>
						<FileText class="mr-2 h-4 w-4" />
						Read Full Article
					</Button>
					<Button
						variant="outline"
						size="sm"
						href={summaryArticle.link}
						target="_blank"
						rel="noopener noreferrer"
						class="w-full sm:w-auto"
					>
						<ExternalLink class="mr-2 h-4 w-4" />
						Open Original
					</Button>
				</div>
			{/if}
		</div>
	</Dialog>
{/if}

<style>
	.prose :global(p) {
		margin-bottom: 1em;
	}
</style>
