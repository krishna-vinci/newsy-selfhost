<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { ModeWatcher } from 'mode-watcher';
	import { Toaster } from 'svelte-sonner';
	import AuthDialog from '$lib/components/auth/AuthDialog.svelte';
	import NotificationBell from '$lib/components/NotificationBell.svelte';
	import Navbar from '$lib/components/Navbar.svelte';
	import SunIcon from '@lucide/svelte/icons/sun';
	import MoonIcon from '@lucide/svelte/icons/moon';

	import { openAuthDialog } from '$lib/stores/auth-dialog.ts';
	import { toggleMode } from 'mode-watcher';
	import Button from '$lib/components/ui/button/index.svelte';

	let { children, data } = $props();
	const authPagePaths = ['/login', '/signup', '/bootstrap'];
	const isLandingRoute = $derived($page.url.pathname.startsWith('/landing'));
	const isAppShellRoute = $derived.by(
		() => data.auth.isAuthenticated && !authPagePaths.includes($page.url.pathname)
	);
	const hideMarketingAuthActions = $derived(isLandingRoute);

	onMount(() => {
		if (window.isSecureContext && 'serviceWorker' in navigator) {
			navigator.serviceWorker.register('/service-worker.js').catch((error) => {
				console.error('Service worker registration failed:', error);
			});
		}
	});
</script>

<ModeWatcher />
<Toaster richColors />
<AuthDialog allowPublicSignup={data.auth.allowPublicSignup} />

<div class="flex h-screen flex-col">
	{#if !isLandingRoute}
	<header class="flex-shrink-0 border-b px-4 py-2 sm:px-6 sm:py-3">
		<div class="flex flex-wrap items-center justify-between gap-3 md:flex-nowrap">
			<div class="flex items-center gap-3 md:flex-1">
				<a href="/" class="text-xl font-bold sm:text-2xl">newsy</a>
			</div>

			<div
				class={isAppShellRoute
					? 'order-3 hidden w-full md:order-2 md:block md:w-auto md:flex-1 md:px-4'
					: 'order-3 w-full md:order-2 md:w-auto md:flex-1 md:px-4'}
			>
				<Navbar user={data.auth.user} />
			</div>

			<div class="order-2 flex items-center gap-2 md:order-3 md:flex-1 md:justify-end">
				{#if data.auth.isAuthenticated}
					<NotificationBell />
				{/if}
				{#if !data.auth.isAuthenticated && !data.auth.bootstrapRequired && !['/login', '/signup', '/bootstrap'].includes($page.url.pathname) && !hideMarketingAuthActions}
					<Button
						variant="outline"
						class="flex-1 sm:flex-none"
						onclick={() => openAuthDialog('login', '/')}
					>
						Sign in
					</Button>
					{#if data.auth.allowPublicSignup}
						<Button class="flex-1 sm:flex-none" onclick={() => openAuthDialog('signup', '/')}>
							Create account
						</Button>
					{/if}
				{/if}
				<Button onclick={toggleMode} variant="outline" size="icon">
					<SunIcon
						class="h-[1.2rem] w-[1.2rem] scale-100 rotate-0 !transition-all dark:scale-0 dark:-rotate-90"
					/>
					<MoonIcon
						class="absolute h-[1.2rem] w-[1.2rem] scale-0 rotate-90 !transition-all dark:scale-100 dark:rotate-0"
					/>
					<span class="sr-only">Toggle theme</span>
				</Button>
			</div>
		</div>
	</header>
	{/if}

	<div class="relative flex-1 overflow-hidden">
		{@render children?.()}
	</div>
</div>
