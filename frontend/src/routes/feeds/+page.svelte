<script lang="ts">
import type { PageData } from './$types.js';
import { invalidateAll } from '$app/navigation';
import { Copy, Eye, LayoutGrid, List, Columns2, ExternalLink, Search, X, Star } from '@lucide/svelte';
import { toast } from 'svelte-sonner';
import Button from '$lib/components/ui/button/index.svelte';
import Badge from '$lib/components/ui/badge/index.svelte';
import Separator from '$lib/components/ui/separator/index.svelte';
import Dialog from '$lib/components/ui/dialog/index.svelte';
import Card from '$lib/components/ui/card/index.svelte';
import Input from '$lib/components/ui/input/index.svelte';
import * as Sidebar from '$lib/components/ui/sidebar/index.js';
import FeedSidebar from '$lib/components/FeedSidebar.svelte';

	let { data }: { data: PageData } = $props();

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
	};
	type Category = {
		category: string;
		feed_items: FeedItem[];
	};

// State
let viewMode = $state<ViewMode>('card');
let selectedCategory = $state<string>('all');
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

// Derived
const categories = $derived(data.categories as Category[] || []);

// Use search results if in search mode, otherwise use original categories
const displayCategories = $derived(isSearchMode ? searchResults : categories);

const filteredArticles = $derived(
		selectedCategory === 'all'
			? displayCategories.flatMap(cat => cat.feed_items)
			: displayCategories.find(cat => cat.category === selectedCategory)?.feed_items || []
	);

// Total search result count (only relevant when searching)
const searchResultCount = $derived(
	isSearchMode ? searchResults.flatMap(cat => cat.feed_items).length : 0
);

	// Functions
	function copyToClipboard(url: string) {
		if (navigator.clipboard && window.isSecureContext) {
			navigator.clipboard.writeText(url)
				.then(() => toast.success('Link copied to clipboard!'))
				.catch(() => toast.error('Failed to copy link'));
		} else {
			// Fallback for non-secure contexts
			const textArea = document.createElement('textarea');
			textArea.value = url;
			textArea.style.position = 'absolute';
			textArea.style.left = '-9999px';
			document.body.appendChild(textArea);
			textArea.select();
			try {
				document.execCommand('copy');
				toast.success('Link copied to clipboard!');
			} catch (err) {
				toast.error('Failed to copy link');
			} finally {
				document.body.removeChild(textArea);
			}
		}
	}

	async function loadArticleContent(url: string) {
		isLoadingContent = true;
		articleContent = '';
		try {
			const response = await fetch(`/article-full-text?url=${encodeURIComponent(url)}`);
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
	}

function handleCategorySelect(category: string) {
selectedCategory = category;
// Re-fetch data with current filters (search, starred, etc.)
if (searchQuery.trim() || isStarredViewActive) {
	fetchFeedsData();
}
}

async function handleConfigChanged() {
await invalidateAll();
}

async function performSearch(query: string) {
	if (!query.trim()) {
		// Clear search - but keep starred view if active
		isSearchMode = isStarredViewActive;
		searchResults = [];
		if (!isStarredViewActive) {
			await invalidateAll();
		} else {
			await fetchFeedsData();
		}
		return;
	}
	
	await fetchFeedsData();
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
	// Keep starred view active if it was on
	if (isStarredViewActive) {
		await fetchFeedsData();
	} else {
		isSearchMode = false;
		searchResults = [];
		await invalidateAll();
	}
}

async function toggleStarredView() {
	isStarredViewActive = !isStarredViewActive;
	await fetchFeedsData();
}

async function fetchFeedsData() {
	const categoryParam = selectedCategory !== 'all' ? `&category=${encodeURIComponent(selectedCategory)}` : '';
	const searchParam = searchQuery.trim() ? `&q=${encodeURIComponent(searchQuery)}` : '';
	const starredParam = isStarredViewActive ? '&starred_only=true' : '';
	
	try {
		const response = await fetch(`/api/feeds?days=2${categoryParam}${searchParam}${starredParam}`);
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

// Keyboard navigation for column view
function handleKeydown(event: KeyboardEvent) {
		if (viewMode !== 'column' || filteredArticles.length === 0) return;
		
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			selectedColumnIndex = Math.min(selectedColumnIndex + 1, filteredArticles.length - 1);
			loadArticleContent(filteredArticles[selectedColumnIndex].link);
		} else if (event.key === 'ArrowUp') {
			event.preventDefault();
			selectedColumnIndex = Math.max(selectedColumnIndex - 1, 0);
			loadArticleContent(filteredArticles[selectedColumnIndex].link);
		}
	}

// Initialize column view
$effect(() => {
if (viewMode === 'column' && filteredArticles.length > 0) {
selectedColumnIndex = 0;
loadArticleContent(filteredArticles[0].link);
}
});
</script>

<style>
    .prose :global(p) {
        margin-bottom: 1em;
    }
</style>

<svelte:window onkeydown={handleKeydown} />

<Sidebar.Provider>
<div class="flex min-h-screen w-full">
<!-- Sidebar -->
<FeedSidebar {selectedCategory} onCategorySelect={handleCategorySelect} onconfigchanged={handleConfigChanged} />

<!-- Main Content -->
<Sidebar.Inset>
<div class="w-full px-8 py-8">
<!-- Header -->
<div class="mb-8 flex flex-col gap-4">
	<div class="flex items-center justify-between gap-4">
		<div class="flex items-center gap-2 min-w-0">
			<Sidebar.Trigger />
			<h1 class="text-2xl font-bold truncate">
				{selectedCategory === 'all' ? 'All Feeds' : selectedCategory}
			</h1>
			{#if isSearchMode && searchQuery}
				<Badge variant="outline" class="text-xs shrink-0">
					{searchResultCount} result{searchResultCount !== 1 ? 's' : ''}
				</Badge>
			{/if}
		</div>

		<div class="flex items-center gap-3 shrink-0">
			<!-- Search Input -->
			<div class="relative w-64">
				<Search class="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
				<Input
					type="text"
					placeholder="Search articles..."
					value={searchQuery}
					oninput={handleSearchInput}
					class="pl-9 pr-9"
					disabled={isSearching}
				/>
				{#if searchQuery}
					<button
						onclick={clearSearch}
						class="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
						aria-label="Clear search"
					>
						<X class="size-4" />
					</button>
				{/if}
			</div>

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

			<!-- View Mode Toggle -->
			<div class="flex gap-2">
				<Button
					variant={viewMode === 'card' ? 'default' : 'outline'}
					size="icon"
					onclick={() => viewMode = 'card'}
					aria-label="Card view"
				>
					<LayoutGrid class="size-4" />
				</Button>
				<Button
					variant={viewMode === 'headline' ? 'default' : 'outline'}
					size="icon"
					onclick={() => viewMode = 'headline'}
					aria-label="Headline view"
				>
					<List class="size-4" />
				</Button>
				<Button
					variant={viewMode === 'column' ? 'default' : 'outline'}
					size="icon"
					onclick={() => viewMode = 'column'}
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
				<Star class="size-16 mb-4 text-muted-foreground" />
				<p class="text-lg text-muted-foreground">No starred articles</p>
				<p class="text-sm text-muted-foreground">
					{selectedCategory === 'all' ? 'Star some articles to see them here' : `No starred articles in ${selectedCategory}`}
				</p>
				<Button variant="outline" class="mt-4" onclick={toggleStarredView}>
					Show All Articles
				</Button>
			{:else if isSearchMode}
				<p class="text-lg text-muted-foreground">No results found for "{searchQuery}"</p>
				<p class="text-sm text-muted-foreground">Try a different search term or clear the search</p>
				<Button variant="outline" class="mt-4" onclick={clearSearch}>
					Clear Search
				</Button>
			{:else}
				<p class="text-lg text-muted-foreground">No articles found</p>
				<p class="text-sm text-muted-foreground">Try selecting a different category</p>
			{/if}
		</div>
	{:else if viewMode === 'card'}
		<!-- Card View -->
		<div class="grid gap-6 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
			{#each filteredArticles as article}
				<Card class="group flex flex-col overflow-hidden transition-all hover:shadow-lg">
					<div class="flex flex-grow flex-col gap-4">
						{#if article.thumbnail}
							<div class="relative -mt-6 -mx-6 overflow-hidden rounded-t-xl">
								<img
									src={article.thumbnail}
									alt={article.title}
									class="h-48 w-full object-cover transition-transform duration-300 group-hover:scale-105"
									onerror={(e) => {
										(e.currentTarget as HTMLImageElement).src = '/default-thumbnail.jpg';
									}}
								/>
							</div>
						{/if}
						<div class="flex flex-grow flex-col justify-between gap-3 px-6">
							<div>
								<div class="flex items-center gap-2">
									<Badge variant="secondary">{article.source}</Badge>
									<span class="text-xs text-muted-foreground">{article.published}</span>
								</div>
								<h3 class="mt-2 line-clamp-2 text-lg font-semibold leading-tight">{article.title}</h3>
								{#if article.description}
									<p class="mt-1 line-clamp-3 text-sm text-muted-foreground">{article.description}</p>
								{/if}
							</div>
							<div class="flex justify-end gap-2">
								<Button
									variant="outline"
									size="icon-sm"
									onclick={(e) => toggleArticleStar(article, e)}
									class={article.starred ? 'text-yellow-500 hover:text-yellow-600' : ''}
								>
									<Star class="size-4" fill={article.starred ? 'currentColor' : 'none'} />
								</Button>
								<Button
									variant="outline"
									size="icon-sm"
									onclick={() => openArticleModal(article)}
								>
									<Eye class="size-4" />
								</Button>
								<Button
									variant="outline"
									size="icon-sm"
									onclick={() => copyToClipboard(article.link)}
								>
									<Copy class="size-4" />
								</Button>
							</div>
						</div>
					</div>
				</Card>
			{/each}
		</div>
	{:else if viewMode === 'headline'}
		<!-- Headline View -->
		<div class="mx-auto">
			<ul class="grid grid-cols-1 gap-4 md:grid-cols-2">
				{#each filteredArticles as article}
					<li class="group flex items-center gap-4 rounded-lg border p-4 transition-all hover:bg-muted">
						<div class="flex min-w-0 flex-1 flex-col gap-1">
							<h3 class="font-semibold leading-snug">{article.title}</h3>
							<div class="flex items-center gap-2 text-xs text-muted-foreground">
								<span>{article.source}</span>
								<span>&bull;</span>
								<span>{article.published}</span>
							</div>
						</div>
						<div class="flex shrink-0 gap-2">
							<Button
								variant="ghost"
								size="icon-sm"
								onclick={(e) => toggleArticleStar(article, e)}
								class={article.starred ? 'text-yellow-500 hover:text-yellow-600' : ''}
							>
								<Star class="size-4" fill={article.starred ? 'currentColor' : 'none'} />
							</Button>
							<Button
								variant="ghost"
								size="icon-sm"
								onclick={() => openArticleModal(article)}
							>
								<Eye class="size-4" />
							</Button>
							<Button
								variant="ghost"
								size="icon-sm"
								onclick={() => copyToClipboard(article.link)}
							>
								<Copy class="size-4" />
							</Button>
						</div>
					</li>
				{/each}
			</ul>
		</div>
	{:else if viewMode === 'column'}
		<!-- Column View -->
		<div class="grid gap-6 lg:grid-cols-2">
			<!-- Article List -->
			<div class="flex flex-col gap-2">
				{#each filteredArticles as article, index}
					<Card
						class="group cursor-pointer transition-all {selectedColumnIndex === index ? 'ring-2 ring-primary' : 'hover:shadow-md'}"
						onclick={() => {
							selectedColumnIndex = index;
							loadArticleContent(article.link);
						}}
					>
						<div class="flex items-start gap-4 px-6 py-4">
							{#if article.thumbnail}
								<img
									src={article.thumbnail}
									alt={article.title}
									class="h-16 w-24 shrink-0 rounded-md object-cover"
									onerror={(e) => {
										(e.currentTarget as HTMLImageElement).src = '/default-thumbnail.jpg';
									}}
								/>
							{/if}
							<div class="flex min-w-0 flex-1 flex-col gap-2">
								<div class="flex items-center gap-2">
									<Badge variant="secondary">{article.source}</Badge>
									<span class="text-xs text-muted-foreground">{article.published}</span>
								</div>
								<h3 class="line-clamp-2 text-base font-semibold leading-snug">{article.title}</h3>
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
			</div>

			<!-- Article Content -->
			<div class="sticky top-4 h-fit">
				<Card class="max-h-[80vh] overflow-auto">
					{#if isLoadingContent}
						<div class="flex items-center justify-center py-16">
							<p class="text-muted-foreground">Loading article...</p>
						</div>
					{:else if filteredArticles[selectedColumnIndex]}
						<div class="flex flex-col gap-4 px-6 py-4">
							<div class="flex items-start justify-between gap-4">
								<div class="flex-1">
									<h2 class="text-xl font-bold leading-tight">{filteredArticles[selectedColumnIndex].title}</h2>
									<div class="mt-2 flex items-center gap-2">
										<Badge variant="secondary">{filteredArticles[selectedColumnIndex].source}</Badge>
										<span class="text-xs text-muted-foreground">{filteredArticles[selectedColumnIndex].published}</span>
									</div>
								</div>
								<div class="flex shrink-0 gap-2">
									<Button
										variant="outline"
										size="icon-sm"
										onclick={(e) => toggleArticleStar(filteredArticles[selectedColumnIndex], e)}
										class={filteredArticles[selectedColumnIndex].starred ? 'text-yellow-500 hover:text-yellow-600' : ''}
									>
										<Star class="size-4" fill={filteredArticles[selectedColumnIndex].starred ? 'currentColor' : 'none'} />
									</Button>
									<Button
										variant="outline"
										size="icon-sm"
										onclick={() => copyToClipboard(filteredArticles[selectedColumnIndex].link)}
									>
										<Copy class="size-4" />
									</Button>
									<Button
										variant="outline"
										size="icon-sm"
										href={filteredArticles[selectedColumnIndex].link}
										target="_blank"
										rel="noopener noreferrer"
									>
										<ExternalLink class="size-4" />
									</Button>
								</div>
							</div>
							<Separator />
							<div class="prose prose-sm max-w-none dark:prose-invert">
								{@html articleContent}
							</div>
						</div>
					{/if}
				</Card>
			</div>
		</div>
	{/if}
</div>
</Sidebar.Inset>
</div>
</Sidebar.Provider>

<!-- Article Modal -->
{#if selectedArticle}
	<Dialog bind:open={modalOpen} title={selectedArticle.title}>
		<div class="flex flex-col gap-4">
			<div class="flex items-center gap-2">
				<Badge variant="secondary">{selectedArticle.source}</Badge>
				<span class="text-xs text-muted-foreground">{selectedArticle.published}</span>
				<div class="ml-auto flex gap-2">
					<Button
						variant="outline"
						size="sm"
						onclick={() => copyToClipboard(selectedArticle!.link)}
					>
						<Copy class="size-4" />
						Copy Link
					</Button>
					<Button
						variant="outline"
						size="sm"
						href={selectedArticle.link}
						target="_blank"
						rel="noopener noreferrer"
					>
						<ExternalLink class="size-4" />
						Open
					</Button>
				</div>
			</div>
			{#if isLoadingContent}
				<div class="flex items-center justify-center py-8">
					<p class="text-muted-foreground">Loading article content...</p>
				</div>
			{:else}
				<div class="prose prose-sm max-w-none dark:prose-invert max-h-[60vh] overflow-auto">
					{@html articleContent}
				</div>
			{/if}
		</div>
	</Dialog>
{/if}
