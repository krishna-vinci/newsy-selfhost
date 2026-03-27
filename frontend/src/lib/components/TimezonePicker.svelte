<script lang="ts">
	import { onMount } from 'svelte';
	import Input from '$lib/components/ui/input/index.svelte';
	import type { TimezoneOption } from '$lib/utils/timezones.ts';
	import { fetchTimezoneOptions, guessBrowserTimezone } from '$lib/utils/timezones.ts';

	let {
		id = 'timezone-search',
		value,
		label = 'Timezone',
		description = 'Search by country, city, or timezone name.',
		placeholder = 'Search country, city, or timezone',
		onChange = (_timezone: string) => {},
		disabled = false,
		showDetectedHint = true
	}: {
		id?: string;
		value: string;
		label?: string;
		description?: string;
		placeholder?: string;
		onChange?: (timezone: string) => void;
		disabled?: boolean;
		showDetectedHint?: boolean;
	} = $props();

	let options = $state<TimezoneOption[]>([]);
	let isLoading = $state(true);
	let loadError = $state('');
	let searchQuery = $state('');
	let browserTimezone = $state('');

	const normalizedSearch = $derived(searchQuery.trim().toLowerCase());
	const selectedOption = $derived(options.find((option) => option.value === value) ?? null);
	const filteredOptions = $derived.by(() => {
		const query = normalizedSearch;
		const ranked = options
			.map((option) => {
				const haystack = [option.value, option.label, option.country, option.region, option.city]
					.filter(Boolean)
					.join(' ')
					.toLowerCase();

				let score = 0;
				if (!query) {
					if (option.value === value) score += 100;
					if (browserTimezone && option.value === browserTimezone) score += 80;
					if (option.value === 'UTC') score += 20;
					if (option.value === 'Asia/Kolkata') score += 10;
				} else if (haystack.includes(query)) {
					score += 1;
					if (option.value.toLowerCase() === query) score += 100;
					if (option.label.toLowerCase().startsWith(query)) score += 40;
					if ((option.country ?? '').toLowerCase().startsWith(query)) score += 30;
					if ((option.city ?? '').toLowerCase().startsWith(query)) score += 20;
				}

				return { option, score };
			})
			.filter((entry) => entry.score > 0)
			.sort((a, b) => b.score - a.score || a.option.label.localeCompare(b.option.label));

		return ranked.slice(0, query ? 60 : 20).map((entry) => entry.option);
	});

	onMount(async () => {
		browserTimezone = guessBrowserTimezone();
		try {
			const payload = await fetchTimezoneOptions();
			options = payload.timezones;
		} catch (error) {
			console.error('Failed to load timezone options', error);
			loadError = 'Unable to load timezones right now.';
		} finally {
			isLoading = false;
		}
	});

	function chooseTimezone(timezone: string) {
		searchQuery = '';
		onChange(timezone);
	}

	function optionMeta(option: TimezoneOption) {
		return [option.value, option.country].filter(Boolean).join(' · ');
	}
</script>

<div class="space-y-2">
	<label class="text-sm font-medium" for={id}>{label}</label>
	{#if description}
		<p class="text-xs text-muted-foreground">{description}</p>
	{/if}

	{#if showDetectedHint && browserTimezone}
		<button
			type="button"
			class="rounded-md bg-muted px-3 py-2 text-left text-xs text-muted-foreground transition hover:bg-muted/80"
			onclick={() => chooseTimezone(browserTimezone)}
			disabled={disabled}
		>
			Use detected timezone: <span class="font-medium text-foreground">{browserTimezone}</span>
		</button>
	{/if}

	<Input id={id} bind:value={searchQuery} {placeholder} disabled={disabled || isLoading} />

	<div class="rounded-lg border bg-background">
		<div class="border-b px-3 py-2 text-xs text-muted-foreground">
			Selected: <span class="font-medium text-foreground">{selectedOption?.label ?? value}</span>
		</div>

		{#if isLoading}
			<div class="px-3 py-4 text-sm text-muted-foreground">Loading timezones…</div>
		{:else if loadError}
			<div class="px-3 py-4 text-sm text-destructive">{loadError}</div>
		{:else if filteredOptions.length === 0}
			<div class="px-3 py-4 text-sm text-muted-foreground">No matching timezones found.</div>
		{:else}
			<div class="max-h-56 overflow-y-auto p-1">
				{#each filteredOptions as option}
					<button
						type="button"
						class={`flex w-full flex-col rounded-md px-3 py-2 text-left transition hover:bg-muted/80 ${option.value === value ? 'bg-muted' : ''}`}
						onclick={() => chooseTimezone(option.value)}
						disabled={disabled}
					>
						<span class="text-sm font-medium">{option.label}</span>
						<span class="text-xs text-muted-foreground">{optionMeta(option)}</span>
					</button>
				{/each}
			</div>
		{/if}
	</div>
</div>
