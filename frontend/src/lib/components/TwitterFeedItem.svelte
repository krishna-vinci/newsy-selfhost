<script lang="ts">
	import Card from "$lib/components/ui/card/index.svelte";

	export let item: {
		title: string;
		link: string;
		description: string;
		thumbnail: string;
		published: string;
	};
</script>

<Card class="p-4 transition-all hover:shadow-md">
	<div class="flex items-start gap-4">
		<!-- Thumbnail -->
		<div class="flex h-12 w-12 items-center justify-center">
			{#if item.thumbnail}
				<img
					src={item.thumbnail}
					alt={item.title}
					class="max-h-full max-w-full rounded-full object-contain"
					onerror={(e) => {
						(e.currentTarget as HTMLImageElement).style.display = "none";
					}}
				/>
			{/if}
		</div>

		<!-- Tweet Content -->
		<div class="flex-1">
			<div class="flex items-center justify-between">
				<a
					href={item.link}
					target="_blank"
					rel="noopener noreferrer"
					class="font-semibold hover:underline"
					title={item.title}
				>
					{item.title}
				</a>
				<span class="text-xs text-muted-foreground">{item.published}</span>
			</div>
			<p class="mt-1 text-sm">{item.description}</p>
		</div>
	</div>
</Card>
