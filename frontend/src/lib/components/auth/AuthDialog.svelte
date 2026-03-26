<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { authDialog, closeAuthDialog, setAuthDialogMode } from '$lib/stores/auth-dialog.ts';
	import AuthPanel from '$lib/components/auth/AuthPanel.svelte';

	let { allowPublicSignup = false }: { allowPublicSignup?: boolean } = $props();
</script>

<Dialog.Root open={$authDialog.open} onOpenChange={(open) => !open && closeAuthDialog()}>
	<Dialog.Content
		class="max-w-[96vw] border-none bg-transparent p-0 shadow-none sm:max-w-5xl"
		showCloseButton={false}
	>
		<Dialog.Title class="sr-only">
			{$authDialog.mode === 'signup' ? 'Create your newsy account' : 'Sign in to newsy'}
		</Dialog.Title>
		<AuthPanel
			mode={$authDialog.mode}
			{allowPublicSignup}
			next={$authDialog.next}
			onModeChange={setAuthDialogMode}
			onSuccess={closeAuthDialog}
		/>
	</Dialog.Content>
</Dialog.Root>
