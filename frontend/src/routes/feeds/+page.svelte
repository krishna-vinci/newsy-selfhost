<script lang="ts">
	import type { PageData } from './$types.js';
	import { Copy, Eye, LayoutGrid, List, Columns2, ExternalLink } from '@lucide/svelte';
	import { toast } from 'svelte-sonner';
	import Button from '$lib/components/ui/button/index.svelte';
	import Badge from '$lib/components/ui/badge/index.svelte';
	import Separator from '$lib/components/ui/separator/index.svelte';
	import * as Select from '$lib/components/ui/select/index.js';
	import Dialog from '$lib/components/ui/dialog/index.svelte';
	import Card from '$lib/components/ui/card/index.svelte';

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

	// Derived
	const categories = $derived(data.categories as Category[] || []);
	const categoryOptions = $derived([
		{ value: 'all', label: 'All Categories' },
		...Array.from(new Set(categories.map(cat => cat.category).filter(Boolean)))
			.map(category => ({ value: category, label: category }))
	]);

	const filteredArticles = $derived(
		selectedCategory === 'all'
			? categories.flatMap(cat => cat.feed_items)
			: categories.find(cat => cat.category === selectedCategory)?.feed_items || []
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

<svelte:window onkeydown={handleKeydown} />

<div class="container mx-auto max-w-7xl px-4 py-8">
	<!-- Header -->
	<div class="mb-8 flex flex-col gap-4">
		<Separator />

		<!-- Filters and View Mode -->
		<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
			<!-- Category Filter -->
			<div class="w-full sm:w-64">
				<Select.Root type="single" bind:value={selectedCategory}>
					<Select.Trigger class="w-full">
						{categoryOptions.find(opt => opt.value === selectedCategory)?.label || 'Select category'}
					</Select.Trigger>
					<Select.Content>
						{#each categoryOptions as option (option.value)}
							<Select.Item value={option.value} label={option.label}>
								{option.label}
							</Select.Item>
						{/each}
					</Select.Content>
				</Select.Root>
			</div>

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

	<!-- Content -->
	{#if filteredArticles.length === 0}
		<div class="flex flex-col items-center justify-center py-16 text-center">
			<p class="text-lg text-muted-foreground">No articles found</p>
			<p class="text-sm text-muted-foreground">Try selecting a different category</p>
		</div>
	{:else if viewMode === 'card'}
		<!-- Card View -->
		<div class="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
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
		<div class="flex flex-col gap-2">
			{#each filteredArticles as article}
				<Card class="group transition-all hover:shadow-md">
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
						<div class="flex shrink-0 gap-2">
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
					</div>
				</Card>
			{/each}
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
