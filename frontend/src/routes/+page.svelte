<script lang="ts">
	import type { PageData } from './$types.js';
	import {
		ArrowRight,
		Clock3,
		ExternalLink,
		FileText,
		LayoutGrid,
		Sparkles,
		Star
	} from '@lucide/svelte';
	import { toast } from 'svelte-sonner';
	import { openAuthDialog } from '$lib/stores/auth-dialog.ts';
	import Button from '$lib/components/ui/button/index.svelte';
	import Card from '$lib/components/ui/card/index.svelte';

	type HomeData = NonNullable<PageData['home']>;
	type Story = HomeData['priorityStories'][number];
	type CategoryPulse = HomeData['categoryPulse'][number];

	const sampleStories: Story[] = [
		{
			title: 'How product teams are quietly reshaping the daily briefing ritual',
			link: '#',
			description:
				'A measured look at why more readers want a smaller, calmer place to start before diving into the full stream.',
			thumbnail: '',
			published: 'Just now',
			published_datetime: new Date().toISOString(),
			source: 'Signal Desk',
			starred: false,
			category: 'Briefing',
			is_read: false
		},
		{
			title: 'Why the best reading tools give you less to process at once',
			link: '#',
			description:
				'High-signal products are leaning into focus, pacing, and the ability to decide when depth is actually necessary.',
			thumbnail: '',
			published: '45m ago',
			published_datetime: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
			source: 'Editorial Systems',
			starred: true,
			category: 'Product',
			is_read: false
		},
		{
			title: 'A practical case for keeping reports, saved reads, and feeds in separate lanes',
			link: '#',
			description:
				'The calmer the first screen feels, the easier it is to trust the rest of the workspace when you need to go deeper.',
			thumbnail: '',
			published: '2h ago',
			published_datetime: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
			source: 'Reader Notes',
			starred: false,
			category: 'Workflow',
			is_read: false
		}
	];

	const sampleSaved: Story[] = [sampleStories[1]];
	const samplePulse: CategoryPulse[] = [
		{ id: 1, name: 'Briefing', priority: 0, ai_enabled: false, unread_count: 6, total_count: 9 },
		{ id: 2, name: 'Product', priority: 1, ai_enabled: true, unread_count: 4, total_count: 7 },
		{ id: 3, name: 'Workflow', priority: 2, ai_enabled: false, unread_count: 3, total_count: 5 }
	];

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
		openAuthDialog('login', '/feeds');
	}

	function openSignUp() {
		openAuthDialog('signup', '/feeds');
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
	const isCaughtUp = $derived(Boolean(isLoggedIn && hasFeeds && (home?.unreadCount ?? 0) === 0));
	const storiesToShow = $derived(isLoggedIn ? priorityStories : sampleStories);
	const savedToShow = $derived(isLoggedIn ? savedStories : sampleSaved);
	const pulseToShow = $derived(isLoggedIn ? (home?.categoryPulse ?? []) : samplePulse);
</script>

<div class="relative h-full overflow-y-auto">
	<div
		class="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(99,102,241,0.08),_transparent_32%),radial-gradient(circle_at_bottom_right,_rgba(148,163,184,0.1),_transparent_30%)]"
	></div>
	<div class="relative mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:py-10">
		<section
			class="overflow-hidden rounded-[2rem] border bg-card/85 p-6 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-card/70 sm:p-8 lg:p-10"
		>
			<div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_260px] lg:items-end">
				<div class="space-y-4">
					<div
						class="inline-flex items-center gap-2 rounded-full border bg-background/80 px-3 py-1 text-xs font-medium text-muted-foreground"
					>
						<Clock3 class="size-3.5" />
						{isLoggedIn
							? `${getGreeting()} — your reading desk is ready.`
							: 'A calmer place to start your reading day.'}
					</div>
					<div class="space-y-3">
						<h1 class="max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
							{#if isLoggedIn}
								{#if isCaughtUp}
									You&apos;re caught up.
								{:else}
									A lighter way to see what matters now.
								{/if}
							{:else}
								Start with the signal, not the flood.
							{/if}
						</h1>
						<p class="max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base">
							{#if isLoggedIn}
								{home?.unreadCount ?? 0} unread item{(home?.unreadCount ?? 0) === 1 ? '' : 's'} across
								{home?.categoryCount ?? 0} categor{(home?.categoryCount ?? 0) === 1 ? 'y' : 'ies'} —
								enough to stay informed without stepping into the full feed wall too early.
							{:else}
								Preview a calmer home built for quick orientation, then sign in when you want the
								full reading workspace behind it.
							{/if}
						</p>
					</div>

					<div class="flex flex-wrap items-center gap-3">
						{#if isLoggedIn}
							<Button href="/feeds" class="rounded-full px-5">
								Continue reading
								<ArrowRight class="size-4" />
							</Button>
							<Button href="/reports" variant="outline" class="rounded-full px-5"
								>Open reports</Button
							>
						{:else}
							<Button class="rounded-full px-5" onclick={openSignIn}>
								Sign in
								<ArrowRight class="size-4" />
							</Button>
							{#if data.auth.allowPublicSignup}
								<Button variant="outline" class="rounded-full px-5" onclick={openSignUp}
									>Create account</Button
								>
							{/if}
						{/if}
					</div>
				</div>

				<div class="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
					<div class="rounded-2xl border bg-background/85 p-4">
						<div class="text-xs tracking-[0.24em] text-muted-foreground uppercase">Unread</div>
						<div class="mt-2 text-3xl font-semibold">
							{isLoggedIn ? (home?.unreadCount ?? 0) : 13}
						</div>
					</div>
					<div class="rounded-2xl border bg-background/85 p-4">
						<div class="text-xs tracking-[0.24em] text-muted-foreground uppercase">
							Recent pulse
						</div>
						<div class="mt-2 text-3xl font-semibold">
							{isLoggedIn ? (home?.recentCount ?? 0) : 21}
						</div>
					</div>
					<div class="rounded-2xl border bg-background/85 p-4">
						<div class="text-xs tracking-[0.24em] text-muted-foreground uppercase">Mode</div>
						<div class="mt-2 flex items-center gap-2 text-sm font-medium">
							<LayoutGrid class="size-4 text-primary" />
							Calm briefing
						</div>
					</div>
				</div>
			</div>
		</section>

		<div class="mt-8 grid gap-8 xl:grid-cols-[minmax(0,1fr)_320px]">
			<div class="space-y-8">
				{#if isLoggedIn && !hasFeeds}
					<Card class="gap-5 px-6 py-6 sm:px-8">
						<div class="space-y-2">
							<div class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase">
								Set up your desk
							</div>
							<h2 class="text-2xl font-semibold tracking-tight">
								There&apos;s nothing to brief yet.
							</h2>
							<p class="max-w-2xl text-sm leading-7 text-muted-foreground">
								Add a few feeds first and this page will turn into your quieter reading layer, with
								just enough signal to help you stay current.
							</p>
						</div>
						<div class="grid gap-4 md:grid-cols-3">
							<div class="rounded-2xl border bg-muted/35 p-5">
								<div class="mb-2 font-medium">Add sources</div>
								<p class="text-sm leading-6 text-muted-foreground">
									Bring in the feeds you care about first.
								</p>
							</div>
							<div class="rounded-2xl border bg-muted/35 p-5">
								<div class="mb-2 font-medium">Shape categories</div>
								<p class="text-sm leading-6 text-muted-foreground">
									Group your incoming reading into calmer lanes.
								</p>
							</div>
							<div class="rounded-2xl border bg-muted/35 p-5">
								<div class="mb-2 font-medium">Return here daily</div>
								<p class="text-sm leading-6 text-muted-foreground">
									Use home as the quick pulse before deeper browsing.
								</p>
							</div>
						</div>
						<div class="flex flex-wrap gap-3">
							<Button href="/feeds">Go to feeds setup</Button>
							<Button href="/reports" variant="outline">Reports</Button>
						</div>
					</Card>
				{:else}
					<Card class="gap-5 px-6 py-6 sm:px-8">
						<div class="flex flex-wrap items-start justify-between gap-4">
							<div class="space-y-2">
								<div
									class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase"
								>
									Priority stories
								</div>
								<h2 class="text-2xl font-semibold tracking-tight">
									{#if isCaughtUp}
										A soft landing for when you&apos;re already on top of things.
									{:else}
										What deserves your attention first.
									{/if}
								</h2>
								<p class="max-w-2xl text-sm leading-7 text-muted-foreground">
									{#if isCaughtUp}
										You can stay here a little longer — the feed can wait until you want more range.
									{:else}
										A smaller set, deliberately surfaced so your first pass stays useful and
										unhurried.
									{/if}
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
												<p class="line-clamp-3 text-sm leading-7 text-muted-foreground">
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
								<div class="rounded-2xl border border-dashed bg-muted/20 p-5 text-sm leading-7 text-muted-foreground">
									There&apos;s nothing pressing right now. Stay here a little longer, revisit a saved story, or open feeds when you want a wider scan.
								</div>
							{/if}
						</div>
					</Card>
				{/if}

				<Card class="gap-5 px-6 py-6 sm:px-8">
					<div class="flex items-start justify-between gap-4">
						<div class="space-y-2">
							<div class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase">
								Digest
							</div>
							<h2 class="text-2xl font-semibold tracking-tight">
								{isLoggedIn ? home?.digest.title : "Today's pulse"}
							</h2>
						</div>
						<div
							class="inline-flex items-center gap-2 rounded-full border bg-muted/40 px-3 py-1 text-xs font-medium text-muted-foreground"
						>
							<Sparkles class="size-3.5 text-primary" />
							{isLoggedIn && home?.aiEnabled ? 'AI-ready' : 'Works without AI'}
						</div>
					</div>

					<p class="max-w-3xl text-base leading-7 text-muted-foreground">
						{isLoggedIn
							? home?.digest.summary
							: 'A smaller pulse can still be rich enough to keep you oriented. Save the full feed sweep for when you genuinely want it.'}
					</p>

					<ul class="grid gap-3 md:grid-cols-3">
						{#each isLoggedIn ? (home?.digest.bullets ?? []) : ['A quick pass should still feel complete, not compromised.', 'Saved reads and reports stay close when you want a slower return.', 'The deeper workspace is one step away, not the default burden.'] as bullet}
							<li
								class="rounded-2xl border bg-muted/30 p-4 text-sm leading-6 text-muted-foreground"
							>
								{bullet}
							</li>
						{/each}
					</ul>
				</Card>
			</div>

			<aside class="space-y-6">
				<Card class="gap-4 px-5 py-5">
					<div class="flex items-center justify-between gap-3">
						<div>
							<div class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase">
								Saved for later
							</div>
							<h2 class="mt-1 text-lg font-semibold">Keep a short queue nearby</h2>
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
							Save a few stories in feeds and they will stay close here for a quieter return later.
						</div>
					{/if}
				</Card>

				<Card class="gap-4 px-5 py-5">
					<div>
						<div class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase">
							Category pulse
						</div>
						<h2 class="mt-1 text-lg font-semibold">Where the movement is</h2>
					</div>

					<div class="space-y-2.5">
						{#each pulseToShow as category}
							<a
								class="flex items-center justify-between rounded-2xl border bg-background/80 px-4 py-3 text-sm transition-colors hover:bg-muted/30"
								href={isLoggedIn ? `/feeds?category=${encodeURIComponent(category.name)}` : '#'}
								onclick={(event) => {
									if (!isLoggedIn) {
										event.preventDefault();
										openSignIn();
									}
								}}
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
							<h2 class="mt-1 text-lg font-semibold">Depth when you need it</h2>
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
							No reports yet. When you want a deeper pass, this space will keep the heavier reading
							organized.
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
	</div>
</div>
