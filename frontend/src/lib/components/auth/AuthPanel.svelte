<script lang="ts">
	import { goto } from '$app/navigation';
	import { ArrowRight, FileText, LayoutGrid, Sparkles } from '@lucide/svelte';
	import Button from '$lib/components/ui/button/index.svelte';
	import Input from '$lib/components/ui/input/index.svelte';
	import type { AuthMode } from '$lib/stores/auth-dialog.ts';

	type FeatureItem = {
		title: string;
		description: string;
		icon: typeof Sparkles;
	};

	const featureItems: FeatureItem[] = [
		{
			title: 'Focused briefings',
			description: 'Catch up fast with a lighter, calmer view before diving into full feeds.',
			icon: Sparkles
		},
		{
			title: 'Flexible reading views',
			description: 'Switch between cards, headlines, and columns to match how you read.',
			icon: LayoutGrid
		},
		{
			title: 'Reports when you need depth',
			description: 'Move from scanning headlines to structured review without losing context.',
			icon: FileText
		}
	];

	let {
		mode = 'login',
		allowPublicSignup = false,
		next = null,
		standalone = false,
		onModeChange = (_mode: AuthMode) => {},
		onSuccess = async () => {}
	}: {
		mode?: AuthMode;
		allowPublicSignup?: boolean;
		next?: string | null;
		standalone?: boolean;
		onModeChange?: (mode: AuthMode) => void;
		onSuccess?: () => Promise<void> | void;
	} = $props();

	let identifier = $state('');
	let username = $state('');
	let email = $state('');
	let password = $state('');
	let errorMessage = $state('');
	let isSubmitting = $state(false);

	const currentMode = $derived(allowPublicSignup ? mode : 'login');
	const isSignupMode = $derived(currentMode === 'signup');
	const loginHref = $derived(next ? `/login?next=${encodeURIComponent(next)}` : '/login');
	const signupHref = $derived(next ? `/signup?next=${encodeURIComponent(next)}` : '/signup');

	$effect(() => {
		currentMode;
		errorMessage = '';
		password = '';
	});

	async function handleSubmit() {
		isSubmitting = true;
		errorMessage = '';

		const endpoint = isSignupMode ? '/api/users' : '/api/auth/sign-in';
		const payload = isSignupMode
			? { username: username.trim(), email: email.trim(), password }
			: { identifier: identifier.trim(), password };

		try {
			const response = await fetch(endpoint, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});

			const result = await response.json().catch(() => ({}));
			if (!response.ok) {
				errorMessage =
					result.detail ||
					result.error ||
					`Unable to ${isSignupMode ? 'create your account' : 'sign in'}.`;
				return;
			}

			await onSuccess();
			await goto(next || '/feeds', { invalidateAll: true });
		} catch (error) {
			console.error(`${isSignupMode ? 'Sign-up' : 'Sign-in'} failed`, error);
			errorMessage = `Unable to ${isSignupMode ? 'create your account' : 'sign in'} right now.`;
		} finally {
			isSubmitting = false;
		}
	}
</script>

<div
	class="overflow-hidden rounded-[2rem] border bg-card/95 text-card-foreground shadow-2xl backdrop-blur supports-[backdrop-filter]:bg-card/90"
>
	<div class="grid lg:grid-cols-[1.08fr_0.92fr]">
		<div
			class="relative hidden min-h-full overflow-hidden border-r bg-muted/40 lg:flex lg:flex-col lg:justify-between"
		>
			<div
				class="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.16),_transparent_42%),radial-gradient(circle_at_bottom_right,_rgba(148,163,184,0.22),_transparent_38%)]"
			></div>
			<div class="relative space-y-10 p-10">
				<div class="space-y-4">
					<div class="text-xs font-semibold tracking-[0.32em] text-muted-foreground uppercase">
						newsy
					</div>
					<h2 class="max-w-lg text-3xl font-semibold tracking-tight text-balance">
						A more composed way to stay informed.
					</h2>
					<p class="max-w-md text-sm leading-6 text-muted-foreground">
						Scan what matters, keep the signal close, and step into the full workspace only when you
						want more depth.
					</p>
				</div>

				<div class="space-y-4">
					{#each featureItems as feature}
						<div class="rounded-2xl border bg-background/85 p-4 shadow-sm">
							<div
								class="mb-3 flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary"
							>
								<feature.icon class="size-5" />
							</div>
							<div class="space-y-1.5">
								<div class="font-medium">{feature.title}</div>
								<p class="text-sm leading-6 text-muted-foreground">{feature.description}</p>
							</div>
						</div>
					{/each}
				</div>
			</div>

			<div class="relative border-t bg-background/65 p-10">
				<div class="space-y-3">
					<div class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase">
						A quick look inside
					</div>
					<div class="space-y-3 rounded-2xl border bg-card p-4 shadow-sm">
						<div class="flex items-center justify-between gap-3">
							<div class="text-sm font-medium">Today&apos;s briefing</div>
							<div class="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
								Quietly focused
							</div>
						</div>
						<div class="space-y-2">
							<div class="h-2 rounded-full bg-muted"></div>
							<div class="h-2 w-4/5 rounded-full bg-muted"></div>
							<div class="h-2 w-2/3 rounded-full bg-muted"></div>
						</div>
						<div class="grid grid-cols-3 gap-2 pt-2 text-xs text-muted-foreground">
							<div class="rounded-xl border bg-background px-3 py-2">Cards</div>
							<div class="rounded-xl border bg-background px-3 py-2">Columns</div>
							<div class="rounded-xl border bg-background px-3 py-2">Reports</div>
						</div>
					</div>
				</div>
			</div>
		</div>

		<div class="p-6 sm:p-8 lg:p-10">
			<div class="mx-auto flex max-w-md flex-col gap-6">
				{#if allowPublicSignup}
					<div class="inline-flex rounded-full border bg-muted/60 p-1">
						{#if standalone}
							<Button
								href={loginHref}
								variant={isSignupMode ? 'ghost' : 'secondary'}
								class="flex-1 rounded-full"
							>
								Sign in
							</Button>
							<Button
								href={signupHref}
								variant={isSignupMode ? 'secondary' : 'ghost'}
								class="flex-1 rounded-full"
							>
								Create account
							</Button>
						{:else}
							<Button
								variant={isSignupMode ? 'ghost' : 'secondary'}
								class="flex-1 rounded-full"
								onclick={() => onModeChange('login')}
							>
								Sign in
							</Button>
							<Button
								variant={isSignupMode ? 'secondary' : 'ghost'}
								class="flex-1 rounded-full"
								onclick={() => onModeChange('signup')}
							>
								Create account
							</Button>
						{/if}
					</div>
				{/if}

				<div class="space-y-2">
					<div class="text-xs font-semibold tracking-[0.28em] text-muted-foreground uppercase">
						{isSignupMode ? 'Set up your reading desk' : 'Welcome back'}
					</div>
					<h1 class="text-3xl font-semibold tracking-tight">
						{isSignupMode ? 'Create your account' : 'Sign in to newsy'}
					</h1>
					<p class="text-sm leading-6 text-muted-foreground">
						{#if isSignupMode}
							Start with a focused home, then move into the full reading workspace when you want
							more depth.
						{:else}
							Step back into your calm briefing and keep the rest of the feed noise at a comfortable
							distance.
						{/if}
					</p>
				</div>

				<form
					class="space-y-4"
					onsubmit={(event) => {
						event.preventDefault();
						handleSubmit();
					}}
				>
					{#if isSignupMode}
						<div class="space-y-2">
							<label class="text-sm font-medium" for="username">Username</label>
							<Input id="username" bind:value={username} autocomplete="username" required />
						</div>

						<div class="space-y-2">
							<label class="text-sm font-medium" for="email">Email</label>
							<Input id="email" type="email" bind:value={email} autocomplete="email" required />
						</div>
					{:else}
						<div class="space-y-2">
							<label class="text-sm font-medium" for="identifier">Username or email</label>
							<Input id="identifier" bind:value={identifier} autocomplete="username" required />
						</div>
					{/if}

					<div class="space-y-2">
						<label class="text-sm font-medium" for="password">Password</label>
						<Input
							id="password"
							type="password"
							bind:value={password}
							autocomplete={isSignupMode ? 'new-password' : 'current-password'}
							required
						/>
					</div>

					{#if isSignupMode}
						<p class="text-xs text-muted-foreground">
							Use at least 12 characters to keep your account secure.
						</p>
					{/if}

					{#if errorMessage}
						<div
							class="rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
						>
							{errorMessage}
						</div>
					{/if}

					<Button class="w-full rounded-xl" type="submit" disabled={isSubmitting}>
						{#if isSubmitting}
							{isSignupMode ? 'Creating account...' : 'Signing in...'}
						{:else}
							{isSignupMode ? 'Create account' : 'Sign in'}
							<ArrowRight class="size-4" />
						{/if}
					</Button>
				</form>

				<div
					class="rounded-2xl border bg-muted/35 p-4 text-sm leading-6 text-muted-foreground lg:hidden"
				>
					<div class="mb-2 font-medium text-foreground">Inside newsy</div>
					Focused briefings, flexible reading layouts, and deeper reports when you want more than a quick
					scan.
				</div>

				{#if allowPublicSignup}
					<p class="text-sm text-muted-foreground">
						{#if isSignupMode}
							Already have an account?
							{#if standalone}
								<a class="font-medium text-primary hover:underline" href={loginHref}>Sign in</a>
							{:else}
								<button
									class="font-medium text-primary hover:underline"
									type="button"
									onclick={() => onModeChange('login')}
								>
									Sign in
								</button>
							{/if}
						{:else}
							Need an account?
							{#if standalone}
								<a class="font-medium text-primary hover:underline" href={signupHref}>Create one</a>
							{:else}
								<button
									class="font-medium text-primary hover:underline"
									type="button"
									onclick={() => onModeChange('signup')}
								>
									Create one
								</button>
							{/if}
						{/if}
					</p>
				{:else}
					<p class="text-sm text-muted-foreground">Public sign-up is disabled for this instance.</p>
				{/if}
			</div>
		</div>
	</div>
</div>
