<script lang="ts">
	import type { PageData } from './$types.js';
	import { goto, invalidateAll } from '$app/navigation';
	import { ArrowRight, ExternalLink, FileText, FolderOpen, Plus, Star } from '@lucide/svelte';
	import { toast } from 'svelte-sonner';
	import { openAuthDialog } from '$lib/stores/auth-dialog.ts';
	import Button from '$lib/components/ui/button/index.svelte';
	import Card from '$lib/components/ui/card/index.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import FeedSidebar from '$lib/components/FeedSidebar.svelte';

	type HomeData = NonNullable<PageData['home']>;
	type Story = HomeData['priorityStories'][number];
	type CategoryPulse = HomeData['categoryPulse'][number];

	let { data }: { data: PageData } = $props();

	let priorityStories = $state<Story[]>(data.home?.priorityStories ?? []);
	let savedStories = $state<Story[]>(data.home?.savedStories ?? []);
	let processingStars = $state<Set<string>>(new Set());

	$effect(() => {
		priorityStories = data.home?.priorityStories ?? [];
		savedStories = data.home?.savedStories ?? [];
	});

	function getGreeting() {
		const hour = new Date().getHours();
		if (hour < 12) return 'Good morning';
		if (hour < 18) return 'Good afternoon';
		return 'Good evening';
	}

	function formatRelativeTime(value: string) {
		const time = new Date(value).getTime();
		if (!time) return '';
		const diff = time - Date.now();
		const minutes = Math.round(diff / 60000);
		const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });

		if (Math.abs(minutes) < 60) return formatter.format(minutes, 'minute');
		const hours = Math.round(minutes / 60);
		if (Math.abs(hours) < 24) return formatter.format(hours, 'hour');
		const days = Math.round(hours / 24);
		return formatter.format(days, 'day');
	}

	function openSignIn() {
		openAuthDialog('login', '/');
	}

	function openSignUp() {
		openAuthDialog('signup', '/');
	}

	function openSidebarCategory(category: string) {
		const target =
			category === 'all' ? '/feeds' : `/feeds?category=${encodeURIComponent(category)}`;
		goto(target);
	}

	function openSidebarFeed() {
		goto('/feeds');
	}

	async function handleSidebarConfigChanged() {
		await invalidateAll();
	}

	function markProcessing(link: string, processing: boolean) {
		const next = new Set(processingStars);
		if (processing) {
			next.add(link);
		} else {
			next.delete(link);
		}
		processingStars = next;
	}

	function updateStoryCollections(link: string, starred: boolean) {
		const sourceStory =
			priorityStories.find((story) => story.link === link) ||
			savedStories.find((story) => story.link === link);

		priorityStories = priorityStories.map((story) =>
			story.link === link ? { ...story, starred } : story
		);
		savedStories = savedStories
			.map((story) => (story.link === link ? { ...story, starred } : story))
			.filter((story) => story.starred);

		if (starred && sourceStory && !savedStories.some((story) => story.link === link)) {
			savedStories = [{ ...sourceStory, starred }, ...savedStories].slice(0, 5);
		}
	}

	async function toggleStar(link: string, starred: boolean) {
		if (!data.auth.isAuthenticated) {
			openSignIn();
			return;
		}

		markProcessing(link, true);
		try {
			const response = await fetch('/api/article/star', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ link, starred })
			});

			if (!response.ok) {
				const payload = await response.json().catch(() => ({}));
				throw new Error(payload.error || 'Unable to update saved state');
			}

			updateStoryCollections(link, starred);
			toast.success(starred ? 'Saved for later' : 'Removed from saved stories');
		} catch (error) {
			console.error('Failed to update saved state', error);
			toast.error(error instanceof Error ? error.message : 'Unable to update saved state');
		} finally {
			markProcessing(link, false);
		}
	}

	const isLoggedIn = $derived(data.auth.isAuthenticated);
	const home = $derived(data.home);
	const hasFeeds = $derived(Boolean(home?.hasFeeds));
	const storiesToShow = $derived(priorityStories);
	const savedToShow = $derived(savedStories);
	const pulseToShow = $derived(home?.categoryPulse ?? []);
</script>

{#snippet homeContent()}
	<section class="rounded-[1.75rem] border bg-card/90 p-6 shadow-sm sm:p-8">
		<div class="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
			<div>
				<div class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase">
					Control center
				</div>
				<h2 class="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Home</h2>
				<p class="mt-2 max-w-2xl text-sm text-muted-foreground sm:text-base">
					{getGreeting()}. Keep up with recent articles, categories, saved stories, and reports.
				</p>
			</div>

			<div class="flex w-full flex-wrap gap-2 lg:w-auto lg:justify-end">
				<Button href="/feeds" class="flex-1 sm:flex-none">
					Open feeds
					<ArrowRight class="size-4" />
				</Button>
				<Button href="/reports" variant="outline" class="flex-1 sm:flex-none">Open reports</Button>
				<Button href="/feeds" variant="outline" class="flex-1 sm:flex-none">
					<Plus class="size-4" />
					Add feed
				</Button>
			</div>
		</div>

		<div class="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
			<div class="rounded-2xl border bg-background/80 p-4">
				<div class="text-xs tracking-[0.24em] text-muted-foreground uppercase">Unread</div>
				<div class="mt-2 text-3xl font-semibold">{home?.unreadCount ?? 0}</div>
			</div>
			<div class="rounded-2xl border bg-background/80 p-4">
				<div class="text-xs tracking-[0.24em] text-muted-foreground uppercase">Recent</div>
				<div class="mt-2 text-3xl font-semibold">{home?.recentCount ?? 0}</div>
			</div>
			<div class="rounded-2xl border bg-background/80 p-4">
				<div class="text-xs tracking-[0.24em] text-muted-foreground uppercase">Categories</div>
				<div class="mt-2 text-3xl font-semibold">{home?.categoryCount ?? 0}</div>
			</div>
			<div class="rounded-2xl border bg-background/80 p-4">
				<div class="text-xs tracking-[0.24em] text-muted-foreground uppercase">Saved</div>
				<div class="mt-2 text-3xl font-semibold">{savedToShow.length}</div>
			</div>
		</div>
	</section>

	<div class="mt-8 grid gap-8 xl:grid-cols-[minmax(0,1fr)_320px]">
		<div class="space-y-8">
			{#if !hasFeeds}
				<Card class="gap-5 px-6 py-6 sm:px-8">
					<div class="space-y-2">
						<div class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase">
							Get started
						</div>
						<h2 class="text-2xl font-semibold tracking-tight">No feeds added yet.</h2>
						<p class="max-w-2xl text-sm leading-7 text-muted-foreground">
							Add a few sources first. Home will become your control view once articles start
							flowing in.
						</p>
					</div>
					<div class="grid gap-4 md:grid-cols-3">
						<div class="rounded-2xl border bg-muted/35 p-5">
							<div class="mb-2 font-medium">Add sources</div>
							<p class="text-sm leading-6 text-muted-foreground">
								Add the feeds you actually want to track.
							</p>
						</div>
						<div class="rounded-2xl border bg-muted/35 p-5">
							<div class="mb-2 font-medium">Organize categories</div>
							<p class="text-sm leading-6 text-muted-foreground">
								Keep your reading grouped into useful buckets.
							</p>
						</div>
						<div class="rounded-2xl border bg-muted/35 p-5">
							<div class="mb-2 font-medium">Use Home</div>
							<p class="text-sm leading-6 text-muted-foreground">
								Come back here for quick status and next actions.
							</p>
						</div>
					</div>
					<div class="flex flex-wrap gap-3">
						<Button href="/feeds">Open feeds</Button>
						<Button href="/reports" variant="outline">Reports</Button>
					</div>
				</Card>
			{:else}
				<Card class="gap-5 px-6 py-6 sm:px-8">
					<div class="flex flex-wrap items-start justify-between gap-4">
						<div class="space-y-2">
							<div class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase">
								Recent unread
							</div>
							<h2 class="text-2xl font-semibold tracking-tight">What to read next</h2>
							<p class="max-w-2xl text-sm leading-7 text-muted-foreground">
								A short working list from your latest unread stories.
							</p>
						</div>
						<Button href="/feeds" variant="outline" class="rounded-full">Open full feeds</Button>
					</div>

					<div class="space-y-4">
						{#if storiesToShow.length > 0}
							{#each storiesToShow as story (story.link)}
								<div class="rounded-2xl border bg-background/80 p-5 shadow-sm">
									<div class="flex items-start justify-between gap-4">
										<div class="min-w-0 flex-1 space-y-3">
											<div class="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
												<span
													class="rounded-full border bg-muted/40 px-2.5 py-1 font-medium text-foreground"
													>{story.source}</span
												>
												<span>{story.category}</span>
												<span>•</span>
												<span>{formatRelativeTime(story.published_datetime)}</span>
											</div>
											<div class="space-y-2">
												<h3 class="text-lg font-semibold tracking-tight text-balance">
													{story.title}
												</h3>
												<p class="line-clamp-2 text-sm leading-6 text-muted-foreground">
													{story.description}
												</p>
											</div>
											<div class="flex flex-wrap items-center gap-3 pt-1 text-sm">
												{#if isLoggedIn}
													<a
														class="inline-flex items-center gap-2 font-medium text-primary hover:underline"
														href={story.link}
														rel="noreferrer"
														target="_blank"
													>
														Read source
														<ExternalLink class="size-4" />
													</a>
												{:else}
													<button
														class="inline-flex items-center gap-2 font-medium text-primary hover:underline"
														type="button"
														onclick={openSignIn}
													>
														Sign in to open
														<ArrowRight class="size-4" />
													</button>
												{/if}
											</div>
										</div>

										{#if isLoggedIn}
											<Button
												size="icon-sm"
												variant={story.starred ? 'secondary' : 'ghost'}
												class={story.starred ? 'text-yellow-600' : ''}
												title={story.starred ? 'Remove from saved' : 'Save for later'}
												aria-label={story.starred ? 'Remove from saved' : 'Save for later'}
												disabled={processingStars.has(story.link)}
												onclick={() => toggleStar(story.link, !story.starred)}
											>
												<Star class="size-4" fill={story.starred ? 'currentColor' : 'none'} />
											</Button>
										{/if}
									</div>
								</div>
							{/each}
						{:else}
							<div
								class="rounded-2xl border border-dashed bg-muted/20 p-5 text-sm leading-7 text-muted-foreground"
							>
								No unread priority stories right now.
							</div>
						{/if}
					</div>
				</Card>
			{/if}

			<Card class="gap-5 px-6 py-6 sm:px-8">
				<div class="flex items-start justify-between gap-4">
					<div>
						<div class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase">
							Categories
						</div>
						<h2 class="mt-1 text-2xl font-semibold tracking-tight">Category overview</h2>
					</div>
					<Button href="/feeds" variant="outline" size="sm">Manage in feeds</Button>
				</div>

				<div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
					{#each pulseToShow as category}
						<button
							type="button"
							class="rounded-2xl border bg-background/80 p-4 text-left transition-colors hover:bg-muted/30"
							onclick={() => openSidebarCategory(category.name)}
						>
							<div class="flex items-start justify-between gap-3">
								<div>
									<div class="font-medium">{category.name}</div>
									<div class="mt-1 text-xs text-muted-foreground">
										{category.total_count} recent · {category.unread_count} unread
									</div>
								</div>
								<div class="rounded-full border px-2 py-1 text-[11px] font-medium">
									{category.ai_enabled ? 'AI on' : 'AI off'}
								</div>
							</div>
						</button>
					{/each}
				</div>
			</Card>
		</div>

		<aside class="space-y-6">
			<Card class="gap-4 px-5 py-5">
				<div class="flex items-center justify-between gap-3">
					<div>
						<div class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase">
							Saved for later
						</div>
						<h2 class="mt-1 text-lg font-semibold">Saved queue</h2>
					</div>
					<Star class="size-4 text-yellow-500" />
				</div>

				{#if savedToShow.length > 0}
					<div class="space-y-3">
						{#each savedToShow as story (story.link)}
							<div class="rounded-2xl border bg-background/80 p-4">
								<div class="mb-1 text-xs text-muted-foreground">
									{story.source} • {formatRelativeTime(story.published_datetime)}
								</div>
								<div class="text-sm leading-6 font-medium text-balance">{story.title}</div>
								<div class="mt-3 flex items-center justify-between gap-3">
									{#if isLoggedIn}
										<a
											class="text-sm font-medium text-primary hover:underline"
											href={story.link}
											rel="noreferrer"
											target="_blank">Open</a
										>
									{:else}
										<button
											class="text-sm font-medium text-primary hover:underline"
											type="button"
											onclick={openSignIn}>Sign in</button
										>
									{/if}

									{#if isLoggedIn}
										<Button
											size="icon-sm"
											variant={story.starred ? 'secondary' : 'ghost'}
											class={story.starred ? 'text-yellow-600' : ''}
											title={story.starred ? 'Remove from saved' : 'Save for later'}
											aria-label={story.starred ? 'Remove from saved' : 'Save for later'}
											disabled={processingStars.has(story.link)}
											onclick={() => toggleStar(story.link, !story.starred)}
										>
											<Star class="size-4" fill={story.starred ? 'currentColor' : 'none'} />
										</Button>
									{/if}
								</div>
							</div>
						{/each}
					</div>
				{:else}
					<div
						class="rounded-2xl border border-dashed bg-muted/20 p-4 text-sm leading-6 text-muted-foreground"
					>
						No saved stories yet.
					</div>
				{/if}
			</Card>

			<Card class="gap-4 px-5 py-5">
				<div>
					<div class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase">
						Quick access
					</div>
					<h2 class="mt-1 text-lg font-semibold">Jump to category</h2>
				</div>

				<div class="space-y-2.5">
					{#each pulseToShow as category}
						<a
							class="flex items-center justify-between rounded-2xl border bg-background/80 px-4 py-3 text-sm transition-colors hover:bg-muted/30"
							href={`/feeds?category=${encodeURIComponent(category.name)}`}
						>
							<div>
								<div class="font-medium">{category.name}</div>
								<div class="text-xs text-muted-foreground">
									{category.total_count} recent item{category.total_count === 1 ? '' : 's'}
								</div>
							</div>
							<div class="rounded-full bg-muted px-2.5 py-1 text-xs font-medium">
								{category.unread_count} unread
							</div>
						</a>
					{/each}
				</div>
			</Card>

			<Card class="gap-4 px-5 py-5">
				<div class="flex items-center justify-between gap-3">
					<div>
						<div class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase">
							Reports
						</div>
						<h2 class="mt-1 text-lg font-semibold">Reports</h2>
					</div>
					<FileText class="size-4 text-primary" />
				</div>

				{#if isLoggedIn && home?.latestReport}
					<div class="rounded-2xl border bg-background/80 p-4">
						<div class="text-xs tracking-[0.24em] text-muted-foreground uppercase">
							Latest report
						</div>
						<div class="mt-2 text-sm font-medium">
							{home.latestReport.category} • {home.latestReport.report_type}
						</div>
						<div class="mt-1 text-sm text-muted-foreground">{home.latestReport.filename}</div>
					</div>
				{:else}
					<div
						class="rounded-2xl border border-dashed bg-muted/20 p-4 text-sm leading-6 text-muted-foreground"
					>
						No reports yet.
					</div>
				{/if}

				{#if isLoggedIn && home?.nextSchedule}
					<div class="rounded-2xl border bg-muted/25 p-4 text-sm text-muted-foreground">
						<div class="mb-1 font-medium text-foreground">Next scheduled report</div>
						{home.nextSchedule}
					</div>
				{/if}

				<Button href="/reports" variant="outline" class="w-full rounded-xl">Open reports</Button>
			</Card>
		</aside>
	</div>
{/snippet}

{#if isLoggedIn}
	<Sidebar.Provider class="h-full">
		<div class="flex h-full w-full">
			<FeedSidebar
				selectedCategory="all"
				selectedFeedUrl={null}
				onCategorySelect={openSidebarCategory}
				onFeedSelect={openSidebarFeed}
				onconfigchanged={handleSidebarConfigChanged}
			/>

			<Sidebar.Inset class="h-full">
				<div class="relative h-full overflow-y-auto">
					<div
						class="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(99,102,241,0.08),_transparent_32%),radial-gradient(circle_at_bottom_right,_rgba(148,163,184,0.1),_transparent_30%)]"
					></div>
					<div class="relative px-4 py-4 sm:px-6 sm:py-6 md:px-8">
						<div class="mx-auto max-w-7xl">
							<div class="mb-6 flex flex-wrap items-center justify-between gap-3 md:mb-8">
								<div class="flex min-w-0 items-center gap-2 sm:gap-3">
									<Sidebar.Trigger class="shrink-0" />
									<div class="min-w-0">
										<div
											class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase"
										>
											Workspace
										</div>
										<h1 class="truncate text-xl font-semibold tracking-tight sm:text-2xl">
											Home briefing
										</h1>
									</div>
								</div>
								<Button href="/feeds" variant="outline" size="sm" class="w-full sm:w-auto">
									Open feeds
								</Button>
							</div>

							{@render homeContent()}
						</div>
					</div>
				</div>
			</Sidebar.Inset>
		</div>
	</Sidebar.Provider>
{:else}
	<div class="relative h-full overflow-y-auto">
		<div
			class="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(99,102,241,0.08),_transparent_32%),radial-gradient(circle_at_bottom_right,_rgba(148,163,184,0.1),_transparent_30%)]"
		></div>
		<div class="relative mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:py-10">
			{@render homeContent()}
		</div>
	</div>
{/if}
