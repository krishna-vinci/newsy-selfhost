<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { Globe, Info, Loader2, Podcast, Rss, Search, Sparkles, Youtube } from '@lucide/svelte';
	import Button from '$lib/components/ui/button/index.svelte';
	import Input from '$lib/components/ui/input/index.svelte';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import * as Select from '$lib/components/ui/select/index.js';

	type DiscoveryMode = 'smart' | 'website' | 'youtube' | 'reddit';

	type DiscoveryFeed = {
		label: string;
		url: string;
		type: string;
		external: boolean;
		count?: number | null;
		description?: string | null;
		is_podcast?: boolean;
		favicon?: string | null;
		site_name?: string | null;
		site_url?: string | null;
		title?: string | null;
		score?: number | null;
		last_updated?: string | null;
		content_type?: string | null;
		version?: string | null;
	};

	type PreviewItem = {
		title: string;
		url: string;
		published: string;
		author: string;
		badge: string;
	};

	type DiscoveryResponse = {
		mode: DiscoveryMode;
		source: 'youtube' | 'reddit' | 'website' | 'smart';
		input: string;
		entity_name: string;
		entity_url?: string | null;
		feeds: DiscoveryFeed[];
		preview_items: PreviewItem[];
		preview_feed_label?: string | null;
		attribution?: {
			label: string;
			url: string;
		} | null;
		metadata?: Record<string, unknown>;
	};

	let {
		categories = [],
		onfeedadded = async () => {}
	}: {
		categories?: string[];
		onfeedadded?: () => Promise<void>;
	} = $props();

	const modes: { value: DiscoveryMode; label: string }[] = [
		{ value: 'smart', label: 'Smart' },
		{ value: 'website', label: 'Website' },
		{ value: 'youtube', label: 'YouTube' },
		{ value: 'reddit', label: 'Reddit' }
	];

	const exampleQueries: Record<DiscoveryMode, string[]> = {
		smart: ['theverge.com', 'veritasium', 'selfhosted'],
		website: ['stratechery.com', 'https://www.theverge.com', 'feeds.feedburner.com/daringfireball'],
		youtube: ['veritasium', 'fireship'],
		reddit: ['selfhosted', 'technology']
	};

	const helperCopy: Record<DiscoveryMode, string> = {
		smart: 'Paste a site, YouTube channel, or subreddit. Newsy will try the right resolver for you.',
		website: 'Paste a full website URL or just a domain. Website discovery may return many feeds.',
		youtube: 'Search by channel name or handle and preview the latest uploads before adding.',
		reddit: 'Search a subreddit and choose the feed flavor you want to follow.'
	};

	let discoveryMode = $state<DiscoveryMode>('smart');
	let discoveryQuery = $state('');
	let discoveryResult = $state<DiscoveryResponse | null>(null);
	let hasSearched = $state(false);
	let isSearching = $state(false);
	let searchError = $state<string | null>(null);
	let showHelperInfo = $state(false);
	let visibleFeedCount = $state(12);
	let activeSearchController = $state<AbortController | null>(null);

	let showAddDialog = $state(false);
	let pendingFeed = $state<DiscoveryFeed | null>(null);
	let pendingFeedSource = $state<'youtube' | 'reddit' | 'website' | 'smart'>('smart');
	let newFeedName = $state('');
	let selectedCategory = $state('');
	let newCategoryName = $state('');
	let useExistingCategory = $state(true);
	let isAddingFeed = $state(false);
	let addingFeedUrls = $state<Set<string>>(new Set());
	let addedFeedUrls = $state<Set<string>>(new Set());

	const normalizedCategories = $derived(
		Array.from(new Set(categories.map((category) => category.trim()).filter(Boolean)))
	);
	const categoryOptions = $derived(
		normalizedCategories.map((category) => ({ value: category, label: category }))
	);
	const visibleFeeds = $derived((discoveryResult?.feeds ?? []).slice(0, visibleFeedCount));
	const hasMoreFeeds = $derived((discoveryResult?.feeds?.length ?? 0) > visibleFeedCount);
	const currentHelperCopy = $derived(helperCopy[discoveryMode]);
	const currentExamples = $derived(exampleQueries[discoveryMode]);
	const ResultIcon = $derived(getModeIcon(discoveryResult?.source ?? discoveryMode));

	$effect(() => {
		if (useExistingCategory && normalizedCategories.length > 0 && !selectedCategory) {
			selectedCategory = normalizedCategories[0];
		}

		if (!normalizedCategories.length) {
			useExistingCategory = false;
		}
	});

	function getPlaceholder(mode: DiscoveryMode) {
		switch (mode) {
			case 'website':
				return 'theverge.com';
			case 'youtube':
				return 'veritasium';
			case 'reddit':
				return 'selfhosted';
			default:
				return 'Search websites, YouTube, or Reddit';
		}
	}

	function formatSourceLabel(source: string) {
		switch (source) {
			case 'youtube':
				return 'YouTube';
			case 'reddit':
				return 'Reddit';
			case 'website':
				return 'Website';
			default:
				return 'Smart';
		}
	}

	function formatDefaultCategory(source: string) {
		switch (source) {
			case 'youtube':
				return 'YouTube';
			case 'reddit':
				return 'Reddit';
			case 'website':
				return 'Web';
			default:
				return 'Reading';
		}
	}

	function getModeIcon(mode: string) {
		switch (mode) {
			case 'youtube':
				return Youtube;
			case 'reddit':
				return Sparkles;
			case 'website':
				return Globe;
			default:
				return Rss;
		}
	}

	function setExample(query: string) {
		discoveryQuery = query;
		void searchFeeds();
	}

	function resetSearchState() {
		searchError = null;
		visibleFeedCount = 12;
	}

	async function searchFeeds() {
		const trimmedQuery = discoveryQuery.trim();
		if (!trimmedQuery) {
			searchError = 'Enter something to discover.';
			discoveryResult = null;
			hasSearched = true;
			return;
		}

		activeSearchController?.abort();
		const controller = new AbortController();
		activeSearchController = controller;

		isSearching = true;
		hasSearched = true;
		resetSearchState();

		try {
			const params = new URLSearchParams({
				mode: discoveryMode,
				query: trimmedQuery,
				include_preview: 'true',
				preview_limit: '4',
				reddit_limit: '10',
				feedsearch_info: 'true',
				feedsearch_favicon: 'true',
				feedsearch_skip_crawl: 'false'
			});

			const response = await fetch(`/api/discovery/search?${params.toString()}`, {
				signal: controller.signal
			});

			const payload = await response.json().catch(() => ({}));
			if (!response.ok) {
				throw new Error(payload.detail || payload.error || 'Unable to search feeds right now');
			}

			discoveryResult = payload as DiscoveryResponse;
			visibleFeedCount = Math.min(12, payload.feeds?.length ?? 12);
		} catch (error) {
			if (controller.signal.aborted) {
				return;
			}

			discoveryResult = null;
			searchError = error instanceof Error ? error.message : 'Unable to search feeds right now';
		} finally {
			if (activeSearchController === controller) {
				activeSearchController = null;
			}
			if (!controller.signal.aborted) {
				isSearching = false;
			}
		}
	}

	function handleSearchSubmit(event: SubmitEvent) {
		event.preventDefault();
		void searchFeeds();
	}

	function openAddDialog(feed: DiscoveryFeed) {
		pendingFeed = feed;
		pendingFeedSource = discoveryResult?.source ?? discoveryMode;
		newFeedName = feed.label || discoveryResult?.entity_name || 'New feed';
		selectedCategory = normalizedCategories[0] ?? '';
		newCategoryName = formatDefaultCategory(discoveryResult?.source ?? discoveryMode);
		useExistingCategory = normalizedCategories.length > 0;
		showAddDialog = true;
	}

	function resetAddDialog() {
		showAddDialog = false;
		pendingFeed = null;
		newFeedName = '';
		selectedCategory = normalizedCategories[0] ?? '';
		newCategoryName = '';
		useExistingCategory = normalizedCategories.length > 0;
		isAddingFeed = false;
	}

	function updateAddingFeed(url: string, adding: boolean) {
		const next = new Set(addingFeedUrls);
		if (adding) {
			next.add(url);
		} else {
			next.delete(url);
		}
		addingFeedUrls = next;
	}

	function markFeedAdded(url: string) {
		addedFeedUrls = new Set([...addedFeedUrls, url]);
	}

	async function addSelectedFeed() {
		if (!pendingFeed) {
			return;
		}

		const targetUrl = pendingFeed.url;

		const category = useExistingCategory ? selectedCategory : newCategoryName.trim();
		const feedName = newFeedName.trim() || pendingFeed.label;

		if (!feedName) {
			toast.error('Feed name is required');
			return;
		}

		if (!category) {
			toast.error('Choose or create a category first');
			return;
		}

		isAddingFeed = true;
		updateAddingFeed(targetUrl, true);

		try {
			const response = await fetch('/api/add-feed', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					url: targetUrl,
					category,
					name: feedName
				})
			});

			const payload = await response.json().catch(() => ({}));
			if (!response.ok) {
				const message = payload.error || payload.detail || 'Failed to add feed';
				if (String(message).toLowerCase().includes('already exists')) {
					markFeedAdded(targetUrl);
				}
				throw new Error(message);
			}

			markFeedAdded(targetUrl);
			toast.success(`Added ${feedName}`, {
				description:
					payload.articles_added != null
						? `${payload.articles_added} recent article${payload.articles_added === 1 ? '' : 's'} imported`
						: 'The feed is now in your library'
			});
			resetAddDialog();
			await onfeedadded();
		} catch (error) {
			toast.error(error instanceof Error ? error.message : 'Failed to add feed');
		} finally {
			isAddingFeed = false;
			updateAddingFeed(targetUrl, false);
		}
	}

	function isKnownFeed(url: string) {
		return addedFeedUrls.has(url);
	}

	function getResultCount() {
		const count = discoveryResult?.feeds?.length ?? 0;
		return `${count} feed${count === 1 ? '' : 's'} found`;
	}

	function feedMetaParts(feed: DiscoveryFeed) {
		return [
			feed.type?.toUpperCase(),
			feed.count != null ? `${feed.count} items` : null,
			feed.is_podcast ? 'Podcast' : null,
			feed.score != null ? `Score ${Math.round(feed.score)}` : null
		].filter(Boolean);
	}

	function handleDialogChange(open: boolean) {
		if (!open) {
			resetAddDialog();
		}
	}
</script>

<section class="space-y-4 sm:space-y-5">
	<div class="rounded-[2rem] border border-border/70 bg-background/90 p-3 shadow-[0_20px_60px_-30px_rgba(15,23,42,0.45)] backdrop-blur sm:p-4">
		<div class="space-y-4">
			<div class="flex items-start gap-3">
				<div class="flex size-11 shrink-0 items-center justify-center rounded-[1.2rem] bg-gradient-to-br from-primary/15 via-primary/5 to-background text-primary">
					<Sparkles class="size-5" />
				</div>
				<div class="min-w-0 flex-1">
					<div class="flex items-center gap-2">
					<h2 class="text-base font-semibold tracking-tight sm:text-lg">Find feeds</h2>
						<Button
							type="button"
							variant="ghost"
							size="icon-sm"
							class="rounded-full text-muted-foreground"
							aria-label="Discovery help"
							title="Discovery help"
							onclick={() => (showHelperInfo = !showHelperInfo)}
						>
							<Info class="size-4" />
						</Button>
					</div>
					{#if showHelperInfo}
						<div class="mt-2 rounded-2xl border bg-muted/25 px-3 py-2 text-xs leading-6 text-muted-foreground">
							{currentHelperCopy}
						</div>
					{/if}
				</div>
			</div>

			<form class="space-y-3" onsubmit={handleSearchSubmit}>
				<div class="overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
					<div class="flex w-max gap-2">
						{#each modes as mode}
							<button
								type="button"
								class={
									discoveryMode === mode.value
										? 'inline-flex items-center rounded-full border border-primary bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary shadow-sm'
										: 'inline-flex items-center rounded-full border bg-background/80 px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted/40 hover:text-foreground'
								}
								onclick={() => (discoveryMode = mode.value)}
							>
								{mode.label}
							</button>
						{/each}
					</div>
				</div>

				<div class="flex flex-col gap-3 md:flex-row">
					<div class="relative flex-1">
						<Search class="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-muted-foreground" />
						<Input
							class="h-14 rounded-[1.5rem] border-0 bg-muted/40 pl-11 pr-4 shadow-inner"
							placeholder={getPlaceholder(discoveryMode)}
							bind:value={discoveryQuery}
						/>
					</div>
					<Button class="h-14 rounded-[1.5rem] px-5 sm:px-6" disabled={isSearching} type="submit">
						{#if isSearching}
							<Loader2 class="size-4 animate-spin" />
							Searching
						{:else}
							<Search class="size-4" />
							Discover
						{/if}
					</Button>
				</div>

				<div class="space-y-2 text-xs text-muted-foreground">
					<div class="font-medium">Try one of these</div>
					<div class="overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
						<div class="flex w-max gap-2">
							{#each currentExamples as example}
								<button
									type="button"
									class="rounded-full border bg-background/80 px-2.5 py-1 font-medium text-foreground transition-colors hover:bg-muted/40"
									onclick={() => setExample(example)}
								>
									{example}
								</button>
							{/each}
						</div>
					</div>
				</div>
			</form>
		</div>
	</div>

	{#if searchError}
		<div class="rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
			{searchError}
		</div>
	{/if}

	{#if discoveryResult}
		<div class="space-y-4 rounded-[1.6rem] border border-border/70 bg-card/95 p-4 shadow-sm sm:p-5">
			<div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
				<div class="space-y-2">
					<div class="flex flex-wrap items-center gap-2 text-xs text-muted-foreground uppercase">
						<span class="rounded-full border bg-muted/40 px-2.5 py-1 font-semibold text-foreground">
							{formatSourceLabel(discoveryResult.source)}
						</span>
						<span>{getResultCount()}</span>
					</div>
					<div>
						<h2 class="text-xl font-semibold tracking-tight sm:text-2xl">
							{discoveryResult.entity_name}
						</h2>
						{#if discoveryResult.entity_url}
							<a
								class="text-sm text-primary hover:underline"
								href={discoveryResult.entity_url}
								rel="noreferrer"
								target="_blank"
							>
								{discoveryResult.entity_url}
							</a>
						{/if}
					</div>
				</div>

				{#if discoveryResult.attribution}
					<a
						class="text-xs font-medium text-muted-foreground hover:text-foreground hover:underline"
						href={discoveryResult.attribution.url}
						rel="noreferrer"
						target="_blank"
					>
						via {discoveryResult.attribution.label}
					</a>
				{/if}
			</div>

			{#if discoveryResult.preview_items?.length > 0}
				<div class="rounded-[1.4rem] border bg-muted/15 p-4">
					<div class="mb-3 text-xs font-semibold tracking-[0.24em] text-muted-foreground uppercase">
						{discoveryResult.preview_feed_label || 'Preview'}
					</div>
					<div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
						{#each discoveryResult.preview_items as item (item.url)}
							<a
								class="rounded-[1.2rem] border bg-background/80 p-3 transition-colors hover:bg-background"
								href={item.url}
								rel="noreferrer"
								target="_blank"
							>
								<div class="line-clamp-2 text-sm font-medium leading-6">{item.title}</div>
								<div class="mt-2 text-xs text-muted-foreground">
									{[item.author, item.published, item.badge].filter(Boolean).join(' • ')}
								</div>
							</a>
						{/each}
					</div>
				</div>
			{/if}

			{#if visibleFeeds.length > 0}
				<div class="space-y-3">
					{#each visibleFeeds as feed (feed.url)}
						<div class="rounded-[1.4rem] border bg-background/90 p-4 shadow-sm transition-colors hover:bg-background">
							<div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
								<div class="min-w-0 flex-1 space-y-3">
									<div class="flex items-start gap-3">
										<div class="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-[1rem] border bg-muted/20 text-muted-foreground">
											{#if feed.favicon}
												<img alt="" class="size-full object-cover" src={feed.favicon} />
											{:else if feed.is_podcast}
												<Podcast class="size-4" />
											{:else}
												<ResultIcon class="size-4" />
											{/if}
										</div>

										<div class="min-w-0 flex-1">
											<div class="flex flex-wrap items-center gap-2">
												<h3 class="text-base font-semibold text-balance">{feed.label}</h3>
												{#each feedMetaParts(feed) as part}
													<span class="rounded-full border bg-muted/20 px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
														{part}
													</span>
												{/each}
											</div>
											<div class="mt-1 break-all text-xs text-muted-foreground/90 sm:text-sm">{feed.url}</div>
										</div>
									</div>

									{#if feed.description}
										<p class="line-clamp-2 text-sm leading-6 text-muted-foreground">{feed.description}</p>
									{/if}
								</div>

								<div class="flex shrink-0 flex-col gap-2 sm:flex-row lg:w-auto lg:flex-col">
									<Button
										variant={isKnownFeed(feed.url) ? 'secondary' : 'default'}
										disabled={addingFeedUrls.has(feed.url) || isKnownFeed(feed.url)}
										class="rounded-xl"
										onclick={() => openAddDialog(feed)}
									>
										{#if addingFeedUrls.has(feed.url)}
											<Loader2 class="size-4 animate-spin" />
											Adding
										{:else if isKnownFeed(feed.url)}
											Added
										{:else}
											Add feed
										{/if}
									</Button>
									<Button href={feed.url} rel="noreferrer" target="_blank" variant="outline" class="rounded-xl">
										Open source
									</Button>
								</div>
							</div>
						</div>
					{/each}
				</div>

				{#if hasMoreFeeds}
					<div class="flex justify-center">
						<Button variant="outline" onclick={() => (visibleFeedCount += 12)}>
							Show {Math.min(12, (discoveryResult?.feeds?.length ?? 0) - visibleFeedCount)} more
						</Button>
					</div>
				{/if}
			{:else}
				<div class="rounded-2xl border border-dashed bg-muted/20 px-4 py-6 text-sm text-muted-foreground">
					Nothing matched yet. Try a broader query or switch discovery modes.
				</div>
			{/if}
		</div>
	{:else if hasSearched && !isSearching && !searchError}
		<div class="rounded-2xl border border-dashed bg-muted/20 px-4 py-6 text-sm text-muted-foreground">
			No feeds matched that search. Try a different source type or a broader query.
		</div>
	{/if}
</section>

<Dialog.Root open={showAddDialog} onOpenChange={handleDialogChange}>
	<Dialog.Content class="max-h-[90vh] max-w-lg overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>Add discovered feed</Dialog.Title>
			<Dialog.Description>
				Save this {formatSourceLabel(pendingFeedSource).toLowerCase()} feed into your library.
			</Dialog.Description>
		</Dialog.Header>

		<div class="space-y-4 py-4">
			{#if pendingFeed}
				<div class="rounded-2xl border bg-muted/20 p-4">
					<div class="text-xs font-semibold tracking-[0.24em] text-muted-foreground uppercase">
						Selected feed
					</div>
					<div class="mt-2 font-medium">{pendingFeed.label}</div>
					<div class="mt-1 break-all text-sm text-muted-foreground">{pendingFeed.url}</div>
				</div>
			{/if}

			<div class="space-y-2">
				<label class="text-sm font-medium" for="discovery-feed-name">Feed name</label>
				<Input id="discovery-feed-name" bind:value={newFeedName} placeholder="Feed name" />
			</div>

			<div class="space-y-2">
				<div class="flex items-center justify-between gap-2">
					<div class="text-sm font-medium">Category</div>
					{#if normalizedCategories.length > 0}
						<button
							type="button"
							class="text-xs font-medium text-primary hover:underline"
							onclick={() => (useExistingCategory = !useExistingCategory)}
						>
							{useExistingCategory ? 'Create new category instead' : 'Use an existing category'}
						</button>
					{/if}
				</div>

				{#if useExistingCategory && normalizedCategories.length > 0}
					<Select.Root type="single" bind:value={selectedCategory}>
						<Select.Trigger>
							{categoryOptions.find((option) => option.value === selectedCategory)?.label ||
								'Select category'}
						</Select.Trigger>
						<Select.Content>
							{#each categoryOptions as option (option.value)}
								<Select.Item label={option.label} value={option.value}>{option.label}</Select.Item>
							{/each}
						</Select.Content>
					</Select.Root>
				{:else}
					<Input bind:value={newCategoryName} placeholder="Category name" />
				{/if}
			</div>
		</div>

		<Dialog.Footer>
			<Button disabled={isAddingFeed} onclick={resetAddDialog} type="button" variant="outline">
				Cancel
			</Button>
			<Button disabled={isAddingFeed || !pendingFeed} onclick={addSelectedFeed} type="button">
				{#if isAddingFeed}
					<Loader2 class="size-4 animate-spin" />
					Adding
				{:else}
					Add feed
				{/if}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
