<script lang="ts">
	import { Dialog as DialogPrimitive } from "bits-ui";
	import { cn } from "$lib/utils.js";
	import { X } from "@lucide/svelte";
	import { fade, fly } from "svelte/transition";

	let {
		open = $bindable(false),
		title,
		description,
		children,
		class: className,
		closeButton = true,
		...restProps
	}: {
		open?: boolean;
		title?: string;
		description?: string;
		children?: any;
		class?: string;
		closeButton?: boolean;
	} = $props();
</script>

<DialogPrimitive.Root bind:open {...restProps}>
	<DialogPrimitive.Portal>
		<DialogPrimitive.Overlay
			transition={fade}
			transitionConfig={{ duration: 150 }}
			class="fixed inset-0 z-50 bg-black/50"
		/>
		<DialogPrimitive.Content
			transition={fly}
			transitionConfig={{ y: -20, duration: 200 }}
			class={cn(
				"fixed left-1/2 top-1/2 z-50 w-full max-w-2xl -translate-x-1/2 -translate-y-1/2 rounded-xl border bg-card p-6 shadow-lg",
				className
			)}
		>
			<div class="flex flex-col gap-4">
				{#if title || closeButton}
					<div class="flex items-start justify-between">
						{#if title}
							<DialogPrimitive.Title class="text-lg font-semibold">
								{title}
							</DialogPrimitive.Title>
						{/if}
						{#if closeButton}
							<DialogPrimitive.Close
								class="rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none"
							>
								<X class="size-4" />
								<span class="sr-only">Close</span>
							</DialogPrimitive.Close>
						{/if}
					</div>
				{/if}
				{#if description}
					<DialogPrimitive.Description class="text-sm text-muted-foreground">
						{description}
					</DialogPrimitive.Description>
				{/if}
				<div class="flex-1">
					{@render children?.()}
				</div>
			</div>
		</DialogPrimitive.Content>
	</DialogPrimitive.Portal>
</DialogPrimitive.Root>
