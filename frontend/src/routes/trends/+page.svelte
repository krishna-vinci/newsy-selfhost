<script lang="ts">
	import type { PageData } from './$types.js';
	import { Copy, Eye, LayoutGrid, List, ExternalLink } from '@lucide/svelte';
	import { toast } from 'svelte-sonner';
	import Button from '$lib/components/ui/button/index.svelte';
	import Badge from '$lib/components/ui/badge/index.svelte';
	import Separator from '$lib/components/ui/separator/index.svelte';
	import * as Select from '$lib/components/ui/select/index.js';
	import Dialog from '$lib/components/ui/dialog/index.svelte';
	import Card from '$lib/components/ui/card/index.svelte';

	let { data }: { data: PageData } = $props();

	type ViewMode = 'card' | 'headline';
	type FeedItem = {
		title: string;
		link: string;
		description: string;
		thumbnail: string;
		published: string;
	};
	type Channel = {
		name: string;
		feed_items: FeedItem[];
	};

	// State
	let viewMode = $state<ViewMode>('card');
	let selectedChannel = $state<string>('');
	let modalOpen = $state(false);
	let selectedArticle = $state<FeedItem | null>(null);
	let articleContent = $state<string>('');
	let isLoadingContent = $state(false);
	let currentSource = $state<string>('youtube');

	// Derived
	const channels = $derived(data.trends?.channels as Channel[] || []);
	const channelOptions = $derived([
		{ value: 'all', label: 'All Channels' },
		...channels.map(ch => ({ value: ch.name, label: ch.name }))
	]);

	const filteredArticles = $derived(
		selectedChannel === 'all' || !selectedChannel
			? channels.flatMap(ch => ch.feed_items)
			: channels.find(ch => ch.name === selectedChannel)?.feed_items || []
	);

	// Initialize selected channel
	$effect(() => {
		if (channels.length > 0 && !selectedChannel) {
			selectedChannel = 'all';
		}
	});

	function copyToClipboard(url: string) {
		if (navigator.clipboard && window.isSecureContext) {
			navigator.clipboard.writeText(url)
				.then(() => toast.success('Link copied to clipboard!'))
				.catch(() => toast.error('Failed to copy link'));
		} else {
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
</script>

<div class="container mx-auto max-w-7xl px-4 py-8">
	<!-- Header -->
	<div class="mb-8 flex flex-col gap-4">
		<Separator />

		<!-- Filters and View Mode -->
		<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
			<!-- Channel Filter -->
			<div class="w-full sm:w-64">
				<Select.Root type="single" bind:value={selectedChannel}>
					<Select.Trigger class="w-full">
						{channelOptions.find(opt => opt.value === selectedChannel)?.label || 'Select channel'}
					</Select.Trigger>
					<Select.Content>
						{#each channelOptions as option (option.value)}
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
			</div>
		</div>
	</div>

	<!-- Content -->
	{#if filteredArticles.length === 0}
		<div class="flex flex-col items-center justify-center py-16 text-center">
			<p class="text-lg text-muted-foreground">No articles found</p>
			<p class="text-sm text-muted-foreground">Try selecting a different channel</p>
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
								<span class="text-xs text-muted-foreground">{article.published}</span>
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
							<span class="text-xs text-muted-foreground">{article.published}</span>
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
	{/if}
</div>

<!-- Article Modal -->
{#if selectedArticle}
	<Dialog bind:open={modalOpen} title={selectedArticle.title}>
		<div class="flex flex-col gap-4">
			<div class="flex items-center gap-2">
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
