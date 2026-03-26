<script lang="ts">
	import Dialog from '$lib/components/ui/dialog/index.svelte';
	import * as Table from '$lib/components/ui/table/index.js';
	import Badge from '$lib/components/ui/badge/index.svelte';

	let { open = $bindable() }: { open: boolean } = $props();

	const shortcuts = [
		{ key: '/', description: 'Focus search input' },
		{ key: 's', description: 'Star current article (column view)' },
		{ key: 'o', description: 'Open current article in new tab (column view)' },
		{ key: 'r', description: 'Mark current article as read (column view)' },
		{ key: '1', description: 'Switch to card view' },
		{ key: '2', description: 'Switch to headline view' },
		{ key: '3', description: 'Switch to column view' },
		{ key: 'a', description: 'Toggle AI filter view' },
		{ key: 'f', description: 'Toggle starred/favorites view' },
		{ key: 'h', description: 'Toggle hide read articles' },
		{ key: '↑ / k', description: 'Navigate to previous article (column view)' },
		{ key: '↓ / j', description: 'Navigate to next article (column view)' },
		{ key: '?', description: 'Show this help dialog' },
		{ key: 'Esc', description: 'Blur input fields' }
	];
</script>

<Dialog
	bind:open
	title="Keyboard Shortcuts"
	description="Use these shortcuts to navigate and perform actions faster."
>
	<div class="max-h-[60vh] overflow-y-auto">
		<Table.Root>
			<Table.Header>
				<Table.Row>
					<Table.Head class="w-[120px]">Key</Table.Head>
					<Table.Head>Action</Table.Head>
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each shortcuts as shortcut}
					<Table.Row>
						<Table.Cell>
							<Badge variant="outline" class="font-mono text-sm">{shortcut.key}</Badge>
						</Table.Cell>
						<Table.Cell>{shortcut.description}</Table.Cell>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>
</Dialog>
