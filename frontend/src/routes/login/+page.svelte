<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import Button from '$lib/components/ui/button/index.svelte';
	import Input from '$lib/components/ui/input/index.svelte';

	let identifier = '';
	let password = '';
	let errorMessage = '';
	let isSubmitting = false;

	async function handleSubmit() {
		isSubmitting = true;
		errorMessage = '';

		try {
			const response = await fetch('/api/auth/sign-in', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ identifier, password })
			});

			const payload = await response.json().catch(() => ({}));
			if (!response.ok) {
				errorMessage = payload.detail || 'Unable to sign in.';
				return;
			}

			await goto($page.url.searchParams.get('next') || '/feeds', { invalidateAll: true });
		} catch (error) {
			console.error('Login failed', error);
			errorMessage = 'Unable to sign in right now.';
		} finally {
			isSubmitting = false;
		}
	}
</script>

<div class="mx-auto flex min-h-full max-w-md items-center px-4 py-12">
	<div class="bg-card text-card-foreground w-full rounded-xl border p-8 shadow-sm">
		<div class="mb-6 space-y-2 text-center">
			<h1 class="text-2xl font-semibold">Sign in</h1>
			<p class="text-sm text-muted-foreground">Use your username or email and password.</p>
		</div>

		<form class="space-y-4" on:submit|preventDefault={handleSubmit}>
			<div class="space-y-2">
				<label class="text-sm font-medium" for="identifier">Username or email</label>
				<Input id="identifier" bind:value={identifier} autocomplete="username" required />
			</div>

			<div class="space-y-2">
				<label class="text-sm font-medium" for="password">Password</label>
				<Input id="password" type="password" bind:value={password} autocomplete="current-password" required />
			</div>

			{#if errorMessage}
				<p class="text-sm text-destructive">{errorMessage}</p>
			{/if}

			<Button class="w-full" type="submit" disabled={isSubmitting}>
				{isSubmitting ? 'Signing in...' : 'Sign in'}
			</Button>
		</form>

		{#if $page.data.auth?.allowPublicSignup}
			<p class="mt-6 text-center text-sm text-muted-foreground">
				Need an account?
				<a class="font-medium text-primary hover:underline" href="/signup">Create one</a>
			</p>
		{:else}
			<p class="mt-6 text-center text-sm text-muted-foreground">
				Public sign-up is disabled for this instance.
			</p>
		{/if}
	</div>
</div>
