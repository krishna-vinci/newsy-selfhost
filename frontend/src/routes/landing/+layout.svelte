<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import SunIcon from '@lucide/svelte/icons/sun';
	import MoonIcon from '@lucide/svelte/icons/moon';
	import { Github, Menu, X } from '@lucide/svelte';
	import Button from '$lib/components/ui/button/index.svelte';
	import { toggleMode } from 'mode-watcher';

	let { children } = $props();
	let scrollHost = $state<HTMLDivElement | null>(null);
	let mobileOpen = $state(false);
	let scrolled = $state(false);
	let headerVisible = $state(true);

	const navItems = [
		{ label: 'Home', href: '/landing' },
		{ label: 'API-doc', href: '/landing/api-doc' },
		{ label: 'GitHub', href: 'https://github.com/krishna-vinci/newsy-selfhost', external: true },
		{ label: 'Help', href: '/landing/help' }
	];

	onMount(() => {
		let lastY = scrollHost?.scrollTop ?? 0;
		let ticking = false;

		const onScroll = () => {
			if (ticking) return;
			ticking = true;
			requestAnimationFrame(() => {
				const y = scrollHost?.scrollTop ?? 0;
				scrolled = y > 16;
				// Show header when near top or scrolling up
				if (y < 80) {
					headerVisible = true;
				} else if (y < lastY - 4) {
					headerVisible = true;
				} else if (y > lastY + 4) {
					headerVisible = false;
					mobileOpen = false;
				}
				lastY = y;
				ticking = false;
			});
		};
		scrollHost?.addEventListener('scroll', onScroll, { passive: true });
		return () => scrollHost?.removeEventListener('scroll', onScroll);
	});

	function handleNavClick() {
		mobileOpen = false;
	}
</script>

<div class="flex h-screen flex-col">
	<!-- Landing-specific header -->
	<header
		class="fixed top-0 right-0 left-0 z-50 transition-all duration-300 {headerVisible
			? 'translate-y-0'
			: '-translate-y-full'} {scrolled
			? 'border-b border-border/60 bg-background/80 shadow-sm backdrop-blur-xl'
			: 'bg-transparent'}"
	>
		<div class="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
			<a href="/landing" class="text-xl font-bold tracking-tight sm:text-2xl">newsy</a>

			<!-- Desktop nav -->
			<nav class="hidden items-center gap-1 md:flex">
				{#each navItems as item}
					{#if item.external}
						<a
							href={item.href}
							target="_blank"
							rel="noreferrer"
							class="inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
						>
							<Github class="size-3.5" />
							{item.label}
						</a>
					{:else}
						<a
							href={item.href}
							class="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground {$page.url.pathname === item.href ? 'text-foreground' : ''}"
						>
							{item.label}
						</a>
					{/if}
				{/each}
			</nav>

			<div class="flex items-center gap-2">
				<Button onclick={toggleMode} variant="ghost" size="icon" class="size-9">
					<SunIcon
						class="h-[1.1rem] w-[1.1rem] scale-100 rotate-0 !transition-all dark:scale-0 dark:-rotate-90"
					/>
					<MoonIcon
						class="absolute h-[1.1rem] w-[1.1rem] scale-0 rotate-90 !transition-all dark:scale-100 dark:rotate-0"
					/>
					<span class="sr-only">Toggle theme</span>
				</Button>

				<!-- Mobile menu toggle -->
				<Button
					onclick={() => (mobileOpen = !mobileOpen)}
					variant="ghost"
					size="icon"
					class="size-9 md:hidden"
				>
					{#if mobileOpen}
						<X class="size-5" />
					{:else}
						<Menu class="size-5" />
					{/if}
				</Button>
			</div>
		</div>

		<!-- Mobile nav dropdown -->
		{#if mobileOpen}
			<div
				class="border-t border-border/40 bg-background/95 backdrop-blur-xl md:hidden"
			>
				<nav class="mx-auto flex max-w-6xl flex-col px-4 py-3">
					{#each navItems as item}
						{#if item.external}
							<a
								href={item.href}
								target="_blank"
								rel="noreferrer"
								onclick={handleNavClick}
								class="flex items-center gap-2 rounded-md px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
							>
								<Github class="size-4" />
								{item.label}
							</a>
						{:else}
							<a
								href={item.href}
								onclick={handleNavClick}
								class="rounded-md px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
							>
								{item.label}
							</a>
						{/if}
					{/each}
				</nav>
			</div>
		{/if}
	</header>

	<!-- Content with top padding to clear fixed header -->
	<div bind:this={scrollHost} class="relative flex-1 overflow-y-auto pt-14">
		{@render children?.()}
	</div>
</div>
