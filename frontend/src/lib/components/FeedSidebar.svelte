<script lang="ts">
import { onMount } from 'svelte';
import { goto } from '$app/navigation';
import { toast } from 'svelte-sonner';
import { copyToClipboard } from '$lib/utils/clipboard.ts';
import * as Sidebar from '$lib/components/ui/sidebar/index.js';
import Button from '$lib/components/ui/button/index.svelte';
import Input from '$lib/components/ui/input/index.svelte';
import Checkbox from '$lib/components/ui/checkbox/index.svelte';
import * as Select from '$lib/components/ui/select/index.js';
import * as Switch from '$lib/components/ui/switch/index.ts';
import { ChevronDown, Plus, Loader2, Pencil, Trash2, Settings, GripVertical, FileText, Bell, Copy } from '@lucide/svelte';
import { dndzone } from 'svelte-dnd-action';


type Feed = {
	id: number;
	name: string;
	url: string;
	isActive: boolean;
	priority: number;
	retention_days: number | null;
};

type Category = {
	id: number;
	name: string;
	priority: number;
	is_default: boolean;
	ntfy_enabled: boolean;
};

type FeedConfig = Record<string, Feed[]>;

// Props
let {
onCategorySelect = () => {},
onconfigchanged = () => {},
selectedCategory = 'all'
}: {
onCategorySelect?: (category: string) => void;
onconfigchanged?: () => void;
selectedCategory?: string;
} = $props();

// State
let feedConfig = $state<FeedConfig>({});
let isLoading = $state(true);
let isSaving = $state(false);
let expandedCategories = $state<Set<string>>(new Set()); // Start collapsed
let showAddFeedForm = $state(false);

// Edit feed modal state
let showEditFeedModal = $state(false);
let editingFeed = $state<Feed | null>(null);
let editingFeedCategory = $state('');

// Category settings modal state
let showCategorySettingsModal = $state(false);
let categoriesList = $state<Category[]>([]);

// Add feed form state
let newFeedUrl = $state('');
let newFeedName = $state('');
let selectedCategoryForFeed = $state('');
let newCategoryName = $state('');
let useExistingCategory = $state(true);
let newFeedRetentionDays = $state<number | undefined>(undefined);

// Derived
const categories = $derived(Object.keys(feedConfig));
const categoryOptions = $derived(
	categories.map((cat) => ({ value: cat, label: cat }))
);

// Functions
async function loadFeedConfig() {
	isLoading = true;
	try {
		const response = await fetch('/api/feeds/config');
		if (!response.ok) {
			throw new Error('Failed to load feed configuration');
		}
		feedConfig = await response.json();
	} catch (error) {
		toast.error('Failed to load feeds');
		console.error('Error loading feed config:', error);
	} finally {
		isLoading = false;
	}
}

async function loadCategories() {
	try {
		const response = await fetch('/api/categories');
		if (!response.ok) {
			throw new Error('Failed to load categories');
		}
		categoriesList = await response.json();
	} catch (error) {
		toast.error('Failed to load categories');
		console.error('Error loading categories:', error);
	}
}

async function saveFeedConfig() {
	isSaving = true;
	try {
		const response = await fetch('/api/feeds/config', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(feedConfig)
		});

		if (!response.ok) {
			throw new Error('Failed to save feed configuration');
		}

		toast.success('Feed configuration saved');
		onconfigchanged();
	} catch (error) {
		toast.error('Failed to save configuration');
		console.error('Error saving feed config:', error);
	} finally {
		isSaving = false;
	}
}

function toggleCategory(category: string) {
	const newSet = new Set(expandedCategories);
	if (newSet.has(category)) {
		newSet.delete(category);
	} else {
		newSet.add(category);
	}
	expandedCategories = newSet;
}


async function addCustomFeed() {
	if (!newFeedUrl.trim()) {
		toast.error('Please enter a feed URL');
		return;
	}

	if (!newFeedName.trim()) {
		toast.error('Please enter a feed name');
		return;
	}

	const category = useExistingCategory ? selectedCategoryForFeed : newCategoryName.trim();

	if (!category) {
		toast.error('Please select or enter a category');
		return;
	}

	try {
		const response = await fetch('/api/add-feed', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				url: newFeedUrl.trim(),
				category: category,
				name: newFeedName.trim(),
				retention_days: newFeedRetentionDays
			})
		});

		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.error || 'Failed to add feed');
		}

		toast.success('Feed added successfully!');
		resetAddFeedForm();
		await loadFeedConfig();
	} catch (error) {
		toast.error(error instanceof Error ? error.message : 'Failed to add feed');
	}
}

function resetAddFeedForm() {
	newFeedUrl = '';
	newFeedName = '';
	selectedCategoryForFeed = '';
	newCategoryName = '';
	useExistingCategory = true;
	showAddFeedForm = false;
	newFeedRetentionDays = undefined;
}

// Edit/Delete Functions
function openEditModal(feed: Feed, category: string) {
	editingFeed = { ...feed };
	editingFeedCategory = category;
	showEditFeedModal = true;
}

function closeEditModal() {
	showEditFeedModal = false;
	editingFeed = null;
}

async function updateFeed() {
	if (!editingFeed) return;

	isSaving = true;
	try {
		const response = await fetch(`/api/feed/${editingFeed.id}`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				name: editingFeed.name,
				url: editingFeed.url,
				category: editingFeedCategory,
				priority: editingFeed.priority,
				retention_days: editingFeed.retention_days
			})
		});

		if (!response.ok) {
			throw new Error('Failed to update feed');
		}

		toast.success('Feed updated successfully');
		closeEditModal();
		await loadFeedConfig(); // Reload to see changes
	} catch (error) {
		toast.error('Failed to update feed');
		console.error('Error updating feed:', error);
	} finally {
		isSaving = false;
	}
}

async function deleteFeed(feedId: number) {
	if (!confirm('Are you sure you want to delete this feed?')) {
		return;
	}

	isSaving = true;
	try {
		const response = await fetch(`/api/feed/${feedId}`, {
			method: 'DELETE'
		});

		if (!response.ok) {
			throw new Error('Failed to delete feed');
		}

		toast.success('Feed deleted successfully');
		await loadFeedConfig(); // Reload to see changes
	} catch (error) {
		toast.error('Failed to delete feed');
		console.error('Error deleting feed:', error);
	} finally {
		isSaving = false;
	}
}

// Category Settings Functions
function openCategorySettings() {
	loadCategories();
	showCategorySettingsModal = true;
}

function closeCategorySettings() {
	showCategorySettingsModal = false;
}

async function handleDndConsider(e: CustomEvent) {
	categoriesList = e.detail.items;
}

async function handleDndFinalize(e: CustomEvent) {
	categoriesList = e.detail.items;
	const categoryIds = categoriesList.map((cat) => cat.id);

	try {
		const response = await fetch('/api/categories/order', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(categoryIds)
		});
		if (!response.ok) throw new Error('Failed to save order');
		toast.success('Category order saved');
		await loadFeedConfig(); // Reload feeds to reflect new order
	} catch (error) {
		toast.error('Failed to save category order');
	}
}

async function setDefaultCategory(categoryId: number) {
	try {
		const response = await fetch(`/api/category/${categoryId}/default`, {
			method: 'PUT'
		});
		if (!response.ok) throw new Error('Failed to set default');
		toast.success('Default category updated');
		await loadCategories(); // Reload categories to show new default
	} catch (error) {
		toast.error('Failed to set default category');
	}
}

async function deleteCategory(categoryId: number) {
	if (!confirm('Are you sure you want to delete this category and all its feeds?')) {
		return;
	}

	try {
		const response = await fetch(`/api/category/${categoryId}`, {
			method: 'DELETE'
		});
		if (!response.ok) throw new Error('Failed to delete category');
		toast.success('Category deleted');
		await loadCategories();
		await loadFeedConfig();
	} catch (error) {
		toast.error('Failed to delete category');
	}
}

async function toggleCategoryNtfy(category: Category) {
	const previousEnabled = category.ntfy_enabled;
	category.ntfy_enabled = !category.ntfy_enabled;
	
	try {
		const response = await fetch(`/api/category/${category.id}/ntfy`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				ntfy_enabled: category.ntfy_enabled
			})
		});
		
		if (!response.ok) throw new Error('Failed to update ntfy setting');
		toast.success(category.ntfy_enabled ? 'Ntfy notifications enabled' : 'Ntfy notifications disabled');
	} catch (error) {
		category.ntfy_enabled = previousEnabled;
		toast.error('Failed to update ntfy setting');
	}
}


function handleCategoryClick(category: string) {
	onCategorySelect(category);
}

// Lifecycle
onMount(() => {
	loadFeedConfig();
});
</script>

<Sidebar.Root>
	<Sidebar.Content>
		<!-- All Categories Option -->
		<Sidebar.Group>
			<Sidebar.Menu>
				<Sidebar.MenuItem>
					<Sidebar.MenuButton
						onclick={() => handleCategoryClick('all')}
						class={selectedCategory === 'all' ? 'bg-accent' : ''}
					>
						<span class="font-semibold">All Categories</span>
					</Sidebar.MenuButton>
				</Sidebar.MenuItem>
				<Sidebar.MenuItem>
					<Sidebar.MenuButton
						onclick={() => goto('/reports')}
					>
						<FileText class="mr-2 h-4 w-4" />
						<span>Reports</span>
					</Sidebar.MenuButton>
				</Sidebar.MenuItem>
			</Sidebar.Menu>
		</Sidebar.Group>

		<Sidebar.Separator />

		<!-- Loading State -->
		{#if isLoading}
			<Sidebar.Group>
				<div class="flex items-center justify-center py-8">
					<Loader2 class="h-6 w-6 animate-spin text-muted-foreground" />
				</div>
			</Sidebar.Group>
		{:else}
			<!-- Categories and Feeds -->
			{#each categories as category}
				<Sidebar.Group>
					<Sidebar.GroupLabel>
						<button
							type="button"
							onclick={() => toggleCategory(category)}
							class="flex w-full items-center justify-between hover:text-foreground"
						>
							<span
								onclick={(e) => {
									e.stopPropagation();
									handleCategoryClick(category);
								}}
								class="flex-1 text-left {selectedCategory === category ? 'font-semibold text-foreground' : ''}"
							>
								{category}
							</span>
							<ChevronDown
								class="h-4 w-4 transition-transform {expandedCategories.has(category) ? '' : '-rotate-90'}"
							/>
						</button>
					</Sidebar.GroupLabel>

					{#if expandedCategories.has(category)}
						<Sidebar.GroupContent>
							<Sidebar.Menu>
								{#each feedConfig[category] as feed}
									<Sidebar.MenuItem>
										<div class="group flex items-center gap-2 px-2 py-1.5">
											<Checkbox
												bind:checked={feed.isActive}
												onCheckedChange={saveFeedConfig}
												disabled={isSaving}
											/>
											<span
												class="flex-1 cursor-pointer text-sm {feed.isActive ? '' : 'text-muted-foreground line-through'}"
											>
												{feed.name}
											</span>
											<div class="hidden items-center gap-1 group-hover:flex">
												<Button
													variant="ghost"
													size="icon"
													class="h-6 w-6"
													onclick={() => openEditModal(feed, category)}
												>
													<Pencil class="h-3 w-3" />
												</Button>
												<Button
													variant="ghost"
													size="icon"
													class="h-6 w-6"
													onclick={() => deleteFeed(feed.id)}
												>
													<Trash2 class="h-3 w-3" />
												</Button>
											</div>
										</div>
									</Sidebar.MenuItem>
								{/each}
							</Sidebar.Menu>
						</Sidebar.GroupContent>
					{/if}
				</Sidebar.Group>
			{/each}
		{/if}
	</Sidebar.Content>

	<!-- Footer with Add Feed Form -->
	<Sidebar.Footer>
		{#if !showAddFeedForm}
			<div class="flex gap-2">
				<Button onclick={() => (showAddFeedForm = true)} variant="outline" size="sm" class="w-full">
					<Plus class="mr-2 h-4 w-4" />
					Add Feed
				</Button>
				<Button onclick={openCategorySettings} variant="ghost" size="icon" class="h-9 w-9">
					<Settings class="h-4 w-4" />
				</Button>
			</div>
		{:else}
			<div class="space-y-3 p-2">
				<div class="space-y-2">
					<Input
						type="text"
						placeholder="Feed name"
						bind:value={newFeedName}
						class="h-8 text-sm"
					/>
					<Input
						type="url"
						placeholder="Feed URL"
						bind:value={newFeedUrl}
						class="h-8 text-sm"
					/>
					<Input
						type="number"
						placeholder="Retention days (e.g., 30)"
						bind:value={newFeedRetentionDays}
						class="h-8 text-sm"
					/>

					<div class="flex gap-2 text-xs">
						<label class="flex items-center gap-1 cursor-pointer">
							<input
								type="radio"
								bind:group={useExistingCategory}
								value={true}
								class="h-3 w-3"
							/>
							<span>Existing</span>
						</label>
						<label class="flex items-center gap-1 cursor-pointer">
							<input
								type="radio"
								bind:group={useExistingCategory}
								value={false}
								class="h-3 w-3"
							/>
							<span>New</span>
						</label>
					</div>

					{#if useExistingCategory}
						<Select.Root type="single" bind:value={selectedCategoryForFeed}>
							<Select.Trigger class="h-8 text-sm">
								{categoryOptions.find(opt => opt.value === selectedCategoryForFeed)?.label || 'Select category'}
							</Select.Trigger>
							<Select.Content>
								{#each categoryOptions as option (option.value)}
									<Select.Item value={option.value} label={option.label}>
										{option.label}
									</Select.Item>
								{/each}
							</Select.Content>
						</Select.Root>
					{:else}
						<Input
							type="text"
							placeholder="New category"
							bind:value={newCategoryName}
							class="h-8 text-sm"
						/>
					{/if}
				</div>

				<div class="flex gap-2">
					<Button
						onclick={addCustomFeed}
						size="sm"
						class="flex-1"
					>
						Add
					</Button>
					<Button
						onclick={resetAddFeedForm}
						variant="outline"
						size="sm"
						class="flex-1"
					>
						Cancel
					</Button>
				</div>
			</div>
		{/if}
	</Sidebar.Footer>
</Sidebar.Root>

<!-- Edit Feed Modal -->
{#if showEditFeedModal && editingFeed}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
		onclick={(e) => {
			if (e.target === e.currentTarget) closeEditModal();
		}}
	>
		<div class="w-full max-w-md rounded-lg bg-card p-6 shadow-lg">
			<h3 class="mb-4 text-lg font-semibold">Edit Feed</h3>
			<div class="space-y-4">
				<div>
					<label for="edit-feed-name" class="mb-1 block text-sm font-medium">Name</label>
					<Input
						id="edit-feed-name"
						type="text"
						placeholder="Feed name"
						bind:value={editingFeed.name}
					/>
				</div>
				<div>
					<label for="edit-feed-url" class="mb-1 block text-sm font-medium">URL</label>
					<Input id="edit-feed-url" type="url" placeholder="Feed URL" bind:value={editingFeed.url} />
				</div>
				<div>
					<label for="edit-feed-retention" class="mb-1 block text-sm font-medium"
						>Retention (days)</label
					>
					<Input
						id="edit-feed-retention"
						type="number"
						placeholder="Default (30)"
						bind:value={editingFeed.retention_days}
					/>
				</div>
				<div>
					<label for="edit-feed-category" class="mb-1 block text-sm font-medium">Category</label>
					<Select.Root type="single" bind:value={editingFeedCategory}>
						<Select.Trigger>{editingFeedCategory || 'Select category'}</Select.Trigger>
						<Select.Content>
							{#each categoryOptions as option}
								<Select.Item value={option.value}>{option.label}</Select.Item>
							{/each}
						</Select.Content>
					</Select.Root>
				</div>
			</div>
			<div class="mt-6 flex justify-end gap-2">
				<Button variant="outline" onclick={closeEditModal}>Cancel</Button>
				<Button onclick={updateFeed} disabled={isSaving}>
					{#if isSaving}
						<Loader2 class="mr-2 h-4 w-4 animate-spin" />
					{/if}
					Save Changes
				</Button>
			</div>
		</div>
	</div>
{/if}

<!-- Category Settings Modal -->
{#if showCategorySettingsModal}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
		onclick={(e) => {
			if (e.target === e.currentTarget) closeCategorySettings();
		}}
	>
		<div class="w-full max-w-5xl rounded-lg bg-card p-6 shadow-lg">
			<h3 class="mb-4 text-lg font-semibold">Manage Categories</h3>

			<div
				class="mb-4 max-h-[60vh] overflow-y-auto"
				use:dndzone={{ items: categoriesList }}
				onconsider={handleDndConsider}
				onfinalize={handleDndFinalize}
			>
				{#each categoriesList as category (category.id)}
					{@const topicName = `feeds-${category.name.toLowerCase().replace(/\s+/g, '-')}`}
					<div class="mb-3 rounded-md bg-background p-3 border border-border">
						<div class="flex items-center gap-4">
							<GripVertical class="h-5 w-5 cursor-grab text-muted-foreground flex-shrink-0" />
							<span class="font-medium flex-grow min-w-0 truncate">{category.name}</span>

							<div class="flex items-center justify-between gap-2 w-[320px] flex-shrink-0">
								<span class="text-xs text-muted-foreground font-mono bg-muted px-2 py-1 rounded truncate">
									{topicName}
								</span>
								<Button
									variant="ghost"
									size="icon"
									class="h-6 w-6"
									onclick={() => copyToClipboard(topicName, 'Topic copied to clipboard')}
								>
									<Copy class="h-3 w-3" />
								</Button>
							</div>

							<div class="flex items-center gap-2 w-[120px] flex-shrink-0">
								<Bell class="h-4 w-4 text-muted-foreground" />
								<Switch.Switch
									checked={category.ntfy_enabled}
									onCheckedChange={() => toggleCategoryNtfy(category)}
								/>
								<span class="text-xs text-muted-foreground w-6">{category.ntfy_enabled ? 'On' : 'Off'}</span>
							</div>

							<div class="flex items-center gap-2 w-[180px] flex-shrink-0 justify-end">
								<Button
									variant={category.is_default ? 'secondary' : 'ghost'}
									size="sm"
									class="text-xs"
									onclick={() => setDefaultCategory(category.id)}
								>
									{category.is_default ? 'Default' : 'Set Default'}
								</Button>
								<Button
									variant="ghost"
									size="icon"
									class="h-8 w-8 flex-shrink-0"
									onclick={() => deleteCategory(category.id)}
								>
									<Trash2 class="h-4 w-4" />
								</Button>
							</div>
						</div>
					</div>
				{/each}
			</div>

			<div class="mt-6 flex justify-end">
				<Button variant="outline" onclick={closeCategorySettings}>Close</Button>
			</div>
		</div>
	</div>
{/if}
