<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import Button from '$lib/components/ui/button/index.svelte';
	import Input from '$lib/components/ui/input/index.svelte';

	let username = '';
	let email = '';
	let password = '';
	let errorMessage = '';
	let isSubmitting = false;

	async function handleSubmit() {
		isSubmitting = true;
		errorMessage = '';

		try {
			const response = await fetch('/api/users', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username, email, password })
			});

			const payload = await response.json().catch(() => ({}));
			if (!response.ok) {
				errorMessage = payload.detail || 'Unable to create your account.';
				return;
			}

			await goto($page.url.searchParams.get('next') || '/feeds', { invalidateAll: true });
		} catch (error) {
			console.error('Sign-up failed', error);
			errorMessage = 'Unable to create your account right now.';
		} finally {
			isSubmitting = false;
		}
	}
</script>

<div class="mx-auto flex min-h-full max-w-md items-center px-4 py-12">
	<div class="bg-card text-card-foreground w-full rounded-xl border p-8 shadow-sm">
		<div class="mb-6 space-y-2 text-center">
			<h1 class="text-2xl font-semibold">Create your account</h1>
			<p class="text-sm text-muted-foreground">Sign up with a username, email, and strong password.</p>
		</div>

		<form class="space-y-4" on:submit|preventDefault={handleSubmit}>
			<div class="space-y-2">
				<label class="text-sm font-medium" for="username">Username</label>
				<Input id="username" bind:value={username} autocomplete="username" required />
			</div>

			<div class="space-y-2">
				<label class="text-sm font-medium" for="email">Email</label>
				<Input id="email" type="email" bind:value={email} autocomplete="email" required />
			</div>

			<div class="space-y-2">
				<label class="text-sm font-medium" for="password">Password</label>
				<Input id="password" type="password" bind:value={password} autocomplete="new-password" required />
			</div>

			<p class="text-xs text-muted-foreground">Use at least 12 characters.</p>

			{#if errorMessage}
				<p class="text-sm text-destructive">{errorMessage}</p>
			{/if}

			<Button class="w-full" type="submit" disabled={isSubmitting}>
				{isSubmitting ? 'Creating account...' : 'Create account'}
			</Button>
		</form>

		<p class="mt-6 text-center text-sm text-muted-foreground">
			Already have an account?
			<a class="font-medium text-primary hover:underline" href="/login">Sign in</a>
		</p>
	</div>
</div>
