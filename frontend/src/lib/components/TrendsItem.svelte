<script lang="ts">
	import Card from '$lib/components/ui/card/index.svelte';
	import Badge from '$lib/components/ui/badge/index.svelte';

	export let item: {
		title: string;
		link: string;
		description: string;
		thumbnail: string;
		published: string;
	};

	// Function to extract news items from the description HTML
	function extractNewsItems(html: string) {
		const newsItems: { link: string; title: string; source: string }[] = [];
		const ulMatch = /<ul>(.*?)<\/ul>/s.exec(html);
		if (ulMatch) {
			const liMatches = [...ulMatch[1].matchAll(/<li>(.*?)<\/li>/gs)];
			for (const liMatch of liMatches) {
				const aMatch = /<a href="(.*?)".*?>(.*?)<\/a>.*?<font color="#6f6f6f">(.*?)<\/font>/s.exec(
					liMatch[1]
				);
				if (aMatch) {
					newsItems.push({
						link: aMatch[1],
						title: aMatch[2],
						source: aMatch[3]
					});
				}
			}
		}
		return newsItems;
	}

	// Extract data from the item prop
	const newsItems = extractNewsItems(item.description);
	const traffic = item.description.match(/<b>(.*?)<\/b>/)?.[1]?.replace('Approx. ', '').replace(' searches', '') || '';

	// A simple formatter for the 'published' date string
	function formatPublished(published: string) {
		let formatted = published.split('(')[0].trim();
		if (formatted.startsWith('Today at')) {
			return formatted.replace('Today at', '').trim();
		}
		if (formatted.startsWith('Yesterday at')) {
			return 'Yesterday';
		}
		return formatted;
	}
</script>

<Card class="p-4 transition-all hover:shadow-md">
	<div class="grid grid-cols-[minmax(0,3fr),1fr,1fr,minmax(0,2fr),auto] items-center gap-6">
		<!-- Trend Title -->
		<a
			href={item.link}
			target="_blank"
			rel="noopener noreferrer"
			class="truncate font-semibold hover:underline"
			title={item.title}
		>
			{item.title}
		</a>

		<!-- Search Volume -->
		<div class="text-right">
			<p class="font-medium">{traffic}</p>
			<p class="text-xs text-muted-foreground">Searches</p>
		</div>

		<!-- Started -->
		<div class="text-right">
			<p class="font-medium">{formatPublished(item.published)}</p>
			<p class="text-xs text-muted-foreground">Started</p>
		</div>

		<!-- Trend Breakdown -->
		<div>
			{#if newsItems.length > 0}
				<div class="flex flex-wrap items-center gap-1">
					{#each newsItems.slice(0, 2) as newsItem}
						<a
							href={newsItem.link}
							target="_blank"
							rel="noopener noreferrer"
							class="truncate text-sm text-muted-foreground hover:underline"
							title={newsItem.title}
						>
							{newsItem.title}
						</a>
						{#if newsItems.slice(0, 2).length > 1 && newsItems.slice(0, 2).indexOf(newsItem) === 0}
							<span class="text-sm text-muted-foreground">,</span>
						{/if}
					{/each}
					{#if newsItems.length > 2}
						<a
							href={item.link}
							target="_blank"
							rel="noopener noreferrer"
							class="ml-1 text-sm font-medium text-primary hover:underline"
						>
							+{newsItems.length - 2} more
						</a>
					{/if}
				</div>
			{:else}
				<p class="text-sm text-muted-foreground">-</p>
			{/if}
		</div>

		<!-- Thumbnail -->
		<div class="flex h-12 w-24 items-center justify-center">
			{#if item.thumbnail}
				<img
					src={item.thumbnail}
					alt={item.title}
					class="max-h-full max-w-full rounded-md object-contain"
					onerror={(e) => {
						(e.currentTarget as HTMLImageElement).style.display = 'none';
					}}
				/>
			{/if}
		</div>
	</div>
</Card>
