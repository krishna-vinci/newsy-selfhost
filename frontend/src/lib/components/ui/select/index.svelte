<script lang="ts">
	import { Select as SelectPrimitive } from 'bits-ui';
	import { cn } from '$lib/utils.js';
	import { ChevronDown } from '@lucide/svelte';
	import { flyAndScale } from '$lib/utils/transitions.js';

	let {
		value = $bindable(''),
		options = [],
		placeholder = 'Select an option',
		class: className,
		...restProps
	}: {
		value?: string;
		options: { value: string; label: string }[];
		placeholder?: string;
		class?: string;
	} = $props();

	const selectedLabel = $derived(options.find((opt) => opt.value === value)?.label || placeholder);
</script>

<SelectPrimitive.Root
	{...restProps}
	{value}
	onValueChange={(v) => {
		if (v) {
			value = v;
		}
	}}
>
	<SelectPrimitive.Trigger
		class={cn(
			'flex h-9 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50',
			className
		)}
	>
		<span>{selectedLabel}</span>
		<ChevronDown class="size-4 opacity-50" />
	</SelectPrimitive.Trigger>
	<SelectPrimitive.Portal>
		<SelectPrimitive.Content
			class="relative z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md"
		>
			<SelectPrimitive.Viewport class="p-1">
				{#each options as option (option.value)}
					<SelectPrimitive.Item
						value={option.value}
						class="relative flex w-full cursor-default items-center rounded-sm py-1.5 pr-2 pl-2 text-sm outline-none select-none hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
					>
						{option.label}
					</SelectPrimitive.Item>
				{/each}
			</SelectPrimitive.Viewport>
		</SelectPrimitive.Content>
	</SelectPrimitive.Portal>
</SelectPrimitive.Root>
