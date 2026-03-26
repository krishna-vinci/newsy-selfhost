<script lang="ts">
	import { goto } from '$app/navigation';
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
			const response = await fetch('/api/users/bootstrap', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username, email, password })
			});

			const payload = await response.json().catch(() => ({}));
			if (!response.ok) {
				errorMessage = payload.detail || 'Unable to complete setup.';
				return;
			}

			await goto('/feeds', { invalidateAll: true });
		} catch (error) {
			console.error('Bootstrap failed', error);
			errorMessage = 'Unable to complete setup right now.';
		} finally {
			isSubmitting = false;
		}
	}
</script>

<div class="mx-auto flex min-h-full max-w-md items-center px-4 py-12">
	<div class="w-full rounded-xl border bg-card p-8 text-card-foreground shadow-sm">
		<div class="mb-6 space-y-2 text-center">
			<h1 class="text-2xl font-semibold">Bootstrap your first admin</h1>
			<p class="text-sm text-muted-foreground">
				This one-time step creates the first administrator account for the instance.
			</p>
		</div>

		<form class="space-y-4" on:submit|preventDefault={handleSubmit}>
			<div class="space-y-2">
				<label class="text-sm font-medium" for="username">Admin username</label>
				<Input id="username" bind:value={username} autocomplete="username" required />
			</div>

			<div class="space-y-2">
				<label class="text-sm font-medium" for="email">Admin email</label>
				<Input id="email" type="email" bind:value={email} autocomplete="email" required />
			</div>

			<div class="space-y-2">
				<label class="text-sm font-medium" for="password">Admin password</label>
				<Input
					id="password"
					type="password"
					bind:value={password}
					autocomplete="new-password"
					required
				/>
			</div>

			<p class="text-xs text-muted-foreground">
				Use at least 12 characters and keep this account safe.
			</p>

			{#if errorMessage}
				<p class="text-sm text-destructive">{errorMessage}</p>
			{/if}

			<Button class="w-full" type="submit" disabled={isSubmitting}>
				{isSubmitting ? 'Setting up...' : 'Create admin account'}
			</Button>
		</form>
	</div>
</div>
