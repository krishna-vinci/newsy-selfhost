<script lang="ts">
	import Youtube from 'svelte-youtube-embed';

	interface Props {
		htmlContent: string;
	}

	let { htmlContent }: Props = $props();
	let videoIds = $state<string[]>([]);
	let processedContent = $state<string>('');

	// Extract video IDs and clean HTML
	$effect(() => {
		if (!htmlContent) {
			processedContent = '';
			videoIds = [];
			return;
		}

		// Parse HTML to find placeholders
		const parser = new DOMParser();
		const doc = parser.parseFromString(htmlContent, 'text/html');
		const placeholders = doc.querySelectorAll('.youtube-embed-placeholder');
		
		const ids: string[] = [];
		placeholders.forEach((placeholder, index) => {
			const videoId = placeholder.getAttribute('data-youtube-id');
			if (videoId) {
				ids.push(videoId);
				// Replace placeholder with a marker
				const marker = doc.createElement('div');
				marker.className = 'youtube-marker';
				marker.setAttribute('data-index', String(index));
				placeholder.replaceWith(marker);
			}
		});
		
		videoIds = ids;
		processedContent = doc.body.innerHTML;
	});
</script>

<div class="article-content prose prose-sm max-w-none dark:prose-invert">
	{@html processedContent}
	
	{#each videoIds as videoId, index}
		<div class="youtube-embed-wrapper" data-video-index={index}>
			<Youtube id={videoId} />
		</div>
	{/each}
</div>

<style>
	.article-content :global(.youtube-embed-wrapper) {
		margin: 1.5rem 0;
		border-radius: 0.5rem;
		overflow: hidden;
		max-width: 100%;
	}
	
	.article-content :global(p) {
		margin-bottom: 1em;
	}
</style>
