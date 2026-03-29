<script lang="ts">
	import { browser } from '$app/environment';
	import type { PageData } from './$types.js';
	import { afterNavigate, beforeNavigate, goto, invalidateAll } from '$app/navigation';
	import { tick } from 'svelte';
	import { ArrowRight, Plus } from '@lucide/svelte';
	import { openAuthDialog } from '$lib/stores/auth-dialog.ts';
	import FeedDiscoveryBar from '$lib/components/FeedDiscoveryBar.svelte';
	import FeedSidebar from '$lib/components/FeedSidebar.svelte';
	import Button from '$lib/components/ui/button/index.svelte';
	import Card from '$lib/components/ui/card/index.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';

	let { data }: { data: PageData } = $props();

	let scrollHost = $state<HTMLDivElement | null>(null);
	let pendingScrollRestoreFrame = $state<number | null>(null);

	const HOME_SCROLL_KEY = 'newsy:home-scroll:v1';

	function openSignIn() {
		openAuthDialog('login', '/');
	}

	function openSignUp() {
		openAuthDialog('signup', '/');
	}

	function openSidebarCategory(category: string) {
		const target =
			category === 'all' ? '/feeds' : `/feeds?category=${encodeURIComponent(category)}`;
		goto(target, { keepFocus: true, noScroll: true });
	}

	function openSidebarFeed() {
		goto('/feeds', { keepFocus: true, noScroll: true });
	}

	async function handleSidebarConfigChanged() {
		await invalidateAll();
	}

	async function handleDiscoveryFeedAdded() {
		await invalidateAll();
	}

	function persistHomeScrollPosition() {
		if (!browser || !scrollHost) {
			return;
		}

		sessionStorage.setItem(HOME_SCROLL_KEY, String(scrollHost.scrollTop));
	}

	async function restoreHomeScrollPosition() {
		if (!browser) {
			return;
		}

		await tick();

		if (pendingScrollRestoreFrame) {
			window.cancelAnimationFrame(pendingScrollRestoreFrame);
		}

		pendingScrollRestoreFrame = window.requestAnimationFrame(() => {
			pendingScrollRestoreFrame = window.requestAnimationFrame(() => {
				pendingScrollRestoreFrame = null;

				if (!scrollHost) {
					return;
				}

				const savedValue = Number.parseInt(sessionStorage.getItem(HOME_SCROLL_KEY) ?? '0', 10);
				if (Number.isFinite(savedValue) && savedValue > 0) {
					scrollHost.scrollTo({ top: savedValue, behavior: 'auto' });
				}
			});
		});
	}

	$effect(() => {
		if (!browser || !scrollHost) {
			return;
		}

		const node = scrollHost;
		const handlePageHide = () => persistHomeScrollPosition();
		const handleVisibilityChange = () => {
			if (document.visibilityState === 'hidden') {
				persistHomeScrollPosition();
			}
		};
		const handleScroll = () => persistHomeScrollPosition();

		node.addEventListener('scroll', handleScroll, { passive: true });
		window.addEventListener('pagehide', handlePageHide);
		document.addEventListener('visibilitychange', handleVisibilityChange);
		void restoreHomeScrollPosition();

		return () => {
			if (pendingScrollRestoreFrame) {
				window.cancelAnimationFrame(pendingScrollRestoreFrame);
			}
			node.removeEventListener('scroll', handleScroll);
			window.removeEventListener('pagehide', handlePageHide);
			document.removeEventListener('visibilitychange', handleVisibilityChange);
		};
	});

	beforeNavigate(() => {
		persistHomeScrollPosition();
	});

	afterNavigate((navigation) => {
		if (!browser || navigation.to?.url.pathname !== '/') {
			return;
		}

		void restoreHomeScrollPosition();
	});

	const isLoggedIn = $derived(data.auth.isAuthenticated);
	const home = $derived(data.home);
	const savedCount = $derived(home?.savedStories?.length ?? 0);
	const hasFeeds = $derived(Boolean(home?.hasFeeds));
	const statItems = $derived([
		{ label: 'Unread', value: home?.unreadCount ?? 0 },
		{ label: 'Recent', value: home?.recentCount ?? 0 },
		{ label: 'Saved', value: savedCount },
		{ label: 'Categories', value: home?.categoryCount ?? 0 }
	]);
	const discoveryCategoryNames = $derived(
		(home?.discoveryCategories ?? []).map((category) => category.name)
	);
</script>

{#if isLoggedIn}
	<Sidebar.Provider class="h-full min-h-0">
		<div class="flex h-full min-h-0 w-full">
			<FeedSidebar
				selectedCategory="all"
				selectedFeedUrl={null}
				onCategorySelect={openSidebarCategory}
				onFeedSelect={openSidebarFeed}
				onconfigchanged={handleSidebarConfigChanged}
			/>

			<Sidebar.Inset class="h-full min-h-0">
				<div
					bind:this={scrollHost}
					class="relative h-full min-h-0 overflow-y-auto overscroll-y-contain"
				>
					<div class="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(99,102,241,0.08),_transparent_32%),radial-gradient(circle_at_bottom_right,_rgba(148,163,184,0.1),_transparent_30%)]"></div>
					<div class="pointer-events-none absolute top-3 left-3 z-20 sm:top-5 sm:left-5 md:top-6 md:left-6">
						<Sidebar.Trigger
							class="pointer-events-auto size-10 rounded-2xl border bg-background/95 shadow-sm backdrop-blur"
						/>
					</div>
					<div class="relative px-3 py-4 sm:px-5 sm:py-5 md:px-8">
						<div class="mx-auto max-w-4xl space-y-4 pt-12 sm:space-y-5 sm:pt-0">

							<FeedDiscoveryBar
								categories={discoveryCategoryNames}
								onfeedadded={handleDiscoveryFeedAdded}
							/>

							<div class="flex flex-wrap items-center gap-2">
								{#each statItems as item (item.label)}
									<Card class="gap-0 rounded-full border-border/70 bg-card/90 px-3 py-2 shadow-sm">
										<div class="text-[10px] font-medium tracking-[0.18em] text-muted-foreground uppercase">
											{item.label}
										</div>
										<div class="text-sm font-semibold tracking-tight">{item.value}</div>
									</Card>
								{/each}
								<Button href="/feeds" variant="outline" size="sm" class="rounded-full">
									Open feeds
								</Button>
							</div>

							{#if !hasFeeds}
								<Card class="gap-2 rounded-[1.5rem] border-border/70 bg-card/90 px-4 py-4 text-sm text-muted-foreground shadow-sm sm:px-5">
									<div class="font-medium text-foreground">No feeds added yet.</div>
									<div>
										Use discovery above to find feeds, or keep using the sidebar Add Feed modal for direct feed URLs.
									</div>
								</Card>
							{/if}
						</div>
					</div>
				</div>
			</Sidebar.Inset>
		</div>
	</Sidebar.Provider>
{:else}
	<div bind:this={scrollHost} class="relative h-full overflow-y-auto">
		<div class="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(99,102,241,0.08),_transparent_32%),radial-gradient(circle_at_bottom_right,_rgba(148,163,184,0.1),_transparent_30%)]"></div>
		<div class="relative mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:py-12">
			<section class="rounded-[2rem] border bg-card/95 p-6 shadow-sm sm:p-8">
				<div class="space-y-4">
					<div class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase">
						Discover feeds
					</div>
					<h1 class="max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl">
						Search websites, YouTube, and Reddit feeds from one clean home screen.
					</h1>
					<p class="max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base">
						Sign in to discover feeds, add them instantly, and manage everything from your library.
					</p>
					<div class="flex flex-wrap gap-3">
						<Button onclick={openSignIn}>
							Sign in
							<ArrowRight class="size-4" />
						</Button>
						<Button onclick={openSignUp} variant="outline">
							Create account
							<Plus class="size-4" />
						</Button>
					</div>
				</div>
			</section>
		</div>
	</div>
{/if}
