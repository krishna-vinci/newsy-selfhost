<script lang="ts">
	import { page } from '$app/stores';
	import AuthPanel from '$lib/components/auth/AuthPanel.svelte';
</script>

<div class="relative h-full overflow-y-auto">
	<div
		class="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(99,102,241,0.08),_transparent_30%),radial-gradient(circle_at_bottom_right,_rgba(148,163,184,0.12),_transparent_28%)]"
	></div>
	<div class="relative mx-auto flex min-h-full max-w-6xl items-center px-4 py-10 sm:px-6 lg:px-8">
		<AuthPanel
			mode="signup"
			allowPublicSignup={$page.data.auth?.allowPublicSignup}
			next={$page.url.searchParams.get('next')}
			standalone
		/>
	</div>
</div>
