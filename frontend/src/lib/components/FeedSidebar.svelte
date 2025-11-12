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
import * as Tabs from '$lib/components/ui/tabs/index.js';
import * as Dialog from '$lib/components/ui/dialog/index.ts';
import { ChevronDown, Plus, Loader2, Pencil, Trash2, Settings, GripVertical, FileText, Bell, Copy, Database, Download, Upload, FileDown, FileUp, Trash, CheckCircle, Star, Check } from '@lucide/svelte';
import SocialIcons from '@rodneylab/svelte-social-icons';
import { dndzone } from 'svelte-dnd-action';
import { settings } from '$lib/stores/settings';


type Feed = {
	id: number;
	name: string;
	url: string;
	isActive: boolean;
	priority: number;
	retention_days: number | null;
	polling_interval: number;
	unread_count?: number;
};

type Category = {
	id: number;
	name: string;
	priority: number;
	is_default: boolean;
	ntfy_enabled: boolean;
	telegram_enabled: boolean;
	telegram_chat_id: string | null;
	ai_prompt: string | null;
	ai_enabled: boolean;
	unread_count?: number;
	total_count?: number;
};

type FeedConfig = Record<string, Feed[]>;

// Props
let {
onCategorySelect = () => {},
onFeedSelect = () => {},
onconfigchanged = () => {},
selectedCategory = 'all',
selectedFeedUrl = null
}: {
onCategorySelect?: (category: string) => void;
onFeedSelect?: (feedUrl: string, feedName: string) => void;
onconfigchanged?: () => void;
selectedCategory?: string;
selectedFeedUrl?: string | null;
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
let activeTab = $state('categories');
let editingCategoryId = $state<number | null>(null);
let editingCategoryName = $state('');

// Timezone settings state
let selectedTimezone = $state('Asia/Kolkata');

// Preferences state
let selectedDefaultView = $state<'card' | 'headline' | 'column'>('card');

// Backup & Export state
let backups = $state<any[]>([]);
let isLoadingBackups = $state(false);
let isCreatingBackup = $state(false);
let isRestoringBackup = $state(false);

// Add feed form state
let newFeedUrl = $state('');
let newFeedName = $state('');
let selectedCategoryForFeed = $state('');
let newCategoryName = $state('');
let useExistingCategory = $state(true);
let newFeedRetentionDays = $state<number | undefined>(undefined);
let newFeedPollingHours = $state(1);
let newFeedPollingMinutes = $state(0);

// Keyword/Topic filter state
let keywordFilters = $state<any[]>([]);
let showFilterDialog = $state(false);
let editingFilter = $state<any | null>(null);
let filterForm = $state({
	name: '',
	category_id: null as number | null,
	filter_type: 'keyword' as 'keyword' | 'topic',
	filter_value: '',
	auto_star: true,
	auto_notify: true,
	enabled: true
});
let aiFilterSubTab = $state('prompt');

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
		console.log('[Categories] Loaded categories:', categoriesList);
		console.log('[Categories] Sample category:', categoriesList[0]);
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
		const pollingInterval = Math.max(1, newFeedPollingHours * 60 + newFeedPollingMinutes);
		const response = await fetch('/api/add-feed', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				url: newFeedUrl.trim(),
				category: category,
				name: newFeedName.trim(),
				retention_days: newFeedRetentionDays,
				polling_interval: pollingInterval
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
	newFeedPollingHours = 1;
	newFeedPollingMinutes = 0;
}

// Edit/Delete Functions
function openEditModal(feed: Feed, category: string) {
	editingFeed = { 
		...feed,
		// Only set default if polling_interval is null/undefined, not if it's 0 or any other number
		polling_interval: feed.polling_interval ?? 60
	};
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
				retention_days: editingFeed.retention_days,
				polling_interval: editingFeed.polling_interval
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
		closeEditModal(); // Close the edit modal
		await loadFeedConfig(); // Reload to see changes
	} catch (error) {
		toast.error('Failed to delete feed');
		console.error('Error deleting feed:', error);
	} finally {
		isSaving = false;
	}
}

async function markAllFeedAsRead(feedUrl: string, feedName: string, event: Event) {
	event.stopPropagation(); // Prevent triggering feed selection
	
	if (!confirm(`Mark all articles from "${feedName}" as read?`)) {
		return;
	}

	try {
		const response = await fetch('/api/feed/mark-all-read', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ feed_url: feedUrl })
		});

		if (!response.ok) {
			throw new Error('Failed to mark articles as read');
		}

		const result = await response.json();
		toast.success(`Marked ${result.count} articles as read`);
		
		// Reload feed config to update counts
		await loadFeedConfig();
		await loadCategories();
	} catch (error) {
		toast.error('Failed to mark articles as read');
		console.error('Error marking articles as read:', error);
	}
}

// Category Settings Functions
function openCategorySettings() {
	loadCategories();
	loadBackups(); // Load backups when opening settings
	activeTab = 'categories'; // Reset to categories tab
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

async function updateCategoryName(categoryId: number, newName: string) {
	if (!newName.trim()) {
		toast.error('Category name cannot be empty');
		return;
	}

	try {
		const response = await fetch(`/api/category/${categoryId}/name`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: newName.trim() })
		});
		
		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.error || 'Failed to update category name');
		}
		
		toast.success('Category name updated');
		await loadCategories();
		await loadFeedConfig();
	} catch (error) {
		toast.error(error instanceof Error ? error.message : 'Failed to update category name');
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

async function updateCategoryTelegram(category: Category, enabled: boolean, chatId: string | null) {
	const previousEnabled = category.telegram_enabled;
	const previousChatId = category.telegram_chat_id;
	
	category.telegram_enabled = enabled;
	category.telegram_chat_id = chatId;
	
	try {
		const response = await fetch(`/api/category/${category.id}/telegram`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				telegram_enabled: enabled,
				telegram_chat_id: chatId
			})
		});
		
		if (!response.ok) throw new Error('Failed to update telegram settings');
		toast.success(enabled ? 'Telegram notifications enabled' : 'Telegram notifications disabled');
	} catch (error) {
		category.telegram_enabled = previousEnabled;
		category.telegram_chat_id = previousChatId;
		toast.error('Failed to update telegram settings');
	}
}

// AI Filter Functions
async function toggleCategoryAI(category: Category) {
	const previousEnabled = category.ai_enabled;
	category.ai_enabled = !category.ai_enabled;
	
	try {
		const response = await fetch(`/api/category/${category.id}/ai-settings`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				ai_prompt: category.ai_prompt,
				ai_enabled: category.ai_enabled
			})
		});
		
		if (!response.ok) throw new Error('Failed to update AI filter setting');
		
		if (category.ai_enabled) {
			toast.success('AI filter enabled. New articles will be filtered automatically.');
		} else {
			toast.success('AI filter disabled.');
		}
	} catch (error) {
		category.ai_enabled = previousEnabled;
		toast.error('Failed to update AI filter setting');
	}
}

async function saveAIPrompt(category: Category, prompt: string) {
	const previousPrompt = category.ai_prompt;
	category.ai_prompt = prompt;
	
	try {
		const response = await fetch(`/api/category/${category.id}/ai-settings`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				ai_prompt: prompt,
				ai_enabled: category.ai_enabled
			})
		});
		
		if (!response.ok) throw new Error('Failed to save AI prompt');
		
		toast.success('AI prompt saved. New articles will be filtered automatically.');
	} catch (error) {
		category.ai_prompt = previousPrompt;
		toast.error('Failed to save AI prompt');
	}
}

async function reprocessCategory(categoryId: number) {
	try {
		toast.info('Starting reprocessing...');
		const response = await fetch(`/api/category/${categoryId}/reprocess-ai-filter`, {
			method: 'POST'
		});
		
		if (!response.ok) throw new Error('Failed to reprocess category');
		
		const result = await response.json();
		toast.success(`Reprocessing complete! ${result.stats.matched} of ${result.stats.total} articles matched`);
	} catch (error) {
		toast.error('Failed to reprocess category');
	}
}

// Keyword/Topic Filter Functions
async function loadKeywordFilters() {
	try {
		const response = await fetch('/api/filters');
		if (!response.ok) throw new Error('Failed to load filters');
		keywordFilters = await response.json();
	} catch (error) {
		console.error('Error loading keyword filters:', error);
		toast.error('Failed to load keyword filters');
	}
}

function openAddFilterDialog() {
	editingFilter = null;
	filterForm = {
		name: '',
		category_id: null,
		filter_type: 'keyword',
		filter_value: '',
		auto_star: true,
		auto_notify: true,
		enabled: true
	};
	showFilterDialog = true;
}

function editFilter(filter: any) {
	editingFilter = filter;
	filterForm = {
		name: filter.name,
		category_id: filter.category_id,
		filter_type: filter.filter_type,
		filter_value: filter.filter_value,
		auto_star: filter.auto_star,
		auto_notify: filter.auto_notify,
		enabled: filter.enabled
	};
	showFilterDialog = true;
}

async function saveFilter() {
	try {
		if (!filterForm.name.trim() || !filterForm.filter_value.trim()) {
			toast.error('Name and filter value are required');
			return;
		}

		const url = editingFilter ? `/api/filters/${editingFilter.id}` : '/api/filters';
		const method = editingFilter ? 'PUT' : 'POST';

		const response = await fetch(url, {
			method,
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(filterForm)
		});

		if (!response.ok) throw new Error('Failed to save filter');

		toast.success(editingFilter ? 'Filter updated successfully' : 'Filter created successfully');
		showFilterDialog = false;
		await loadKeywordFilters();
	} catch (error) {
		console.error('Error saving filter:', error);
		toast.error('Failed to save filter');
	}
}

async function deleteKeywordFilter(filterId: number) {
	if (!confirm('Are you sure you want to delete this filter?')) return;

	try {
		const response = await fetch(`/api/filters/${filterId}`, {
			method: 'DELETE'
		});

		if (!response.ok) throw new Error('Failed to delete filter');

		toast.success('Filter deleted successfully');
		await loadKeywordFilters();
	} catch (error) {
		console.error('Error deleting filter:', error);
		toast.error('Failed to delete filter');
	}
}

async function updateTimezone(tz: string) {
	const success = await settings.updateTimezone(tz);
	if (success) {
		toast.success('Timezone updated successfully');
	} else {
		toast.error('Failed to update timezone');
	}
}

async function updateDefaultView(view: 'card' | 'headline' | 'column') {
	const success = await settings.updateDefaultView(view);
	if (success) {
		selectedDefaultView = view;
		toast.success('Default view updated successfully');
	} else {
		toast.error('Failed to update default view');
	}
}

// Backup & Export Functions
async function loadBackups() {
	isLoadingBackups = true;
	try {
		const response = await fetch('/api/backups');
		if (response.ok) {
			backups = await response.json();
		}
	} catch (error) {
		toast.error('Failed to load backups');
		console.error(error);
	} finally {
		isLoadingBackups = false;
	}
}

async function createBackup() {
	isCreatingBackup = true;
	try {
		const response = await fetch('/api/backups', { method: 'POST' });
		if (response.ok) {
			toast.success('Backup created successfully');
			await loadBackups();
		} else {
			toast.error('Failed to create backup');
		}
	} catch (error) {
		toast.error('Failed to create backup');
		console.error(error);
	} finally {
		isCreatingBackup = false;
	}
}

async function downloadBackup(filename: string) {
	try {
		window.open(`/api/backups/download/${filename}`, '_blank');
	} catch (error) {
		toast.error('Failed to download backup');
	}
}

async function deleteBackup(filename: string) {
	if (!confirm(`Are you sure you want to delete ${filename}?`)) return;
	
	try {
		const response = await fetch(`/api/backups/${filename}`, { method: 'DELETE' });
		if (response.ok) {
			toast.success('Backup deleted');
			await loadBackups();
		} else {
			toast.error('Failed to delete backup');
		}
	} catch (error) {
		toast.error('Failed to delete backup');
	}
}

async function restoreBackup(filename: string) {
	if (!confirm(`WARNING: This will replace your current database with this backup. Are you sure?`)) return;
	
	isRestoringBackup = true;
	try {
		const response = await fetch('/api/backups/restore', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ filename })
		});
		if (response.ok) {
			toast.success('Database restored successfully. Reloading...');
			setTimeout(() => window.location.reload(), 2000);
		} else {
			toast.error('Failed to restore backup');
		}
	} catch (error) {
		toast.error('Failed to restore backup');
	} finally {
		isRestoringBackup = false;
	}
}

async function exportArticles(format: 'csv' | 'json') {
	try {
		window.open(`/api/export/articles?format=${format}`, '_blank');
		toast.success(`Exporting articles as ${format.toUpperCase()}...`);
	} catch (error) {
		toast.error('Failed to export articles');
	}
}

async function exportOPML() {
	try {
		window.open('/api/opml/export', '_blank');
		toast.success('Exporting feeds as OPML...');
	} catch (error) {
		toast.error('Failed to export OPML');
	}
}

async function importOPML(event: Event) {
	const input = event.target as HTMLInputElement;
	const file = input.files?.[0];
	if (!file) return;
	
	const formData = new FormData();
	formData.append('file', file);
	
	try {
		const response = await fetch('/api/opml/import', {
			method: 'POST',
			body: formData
		});
		
		if (response.ok) {
			const result = await response.json();
			toast.success(`Imported ${result.imported} feeds (${result.skipped} skipped)`);
			await loadFeedConfig();
			onconfigchanged();
		} else {
			toast.error('Failed to import OPML');
		}
	} catch (error) {
		toast.error('Failed to import OPML');
		console.error(error);
	}
	
	// Reset input
	input.value = '';
}

function handleCategoryClick(category: string) {
	onCategorySelect(category);
}

function handleFeedClick(feedUrl: string, feedName: string) {
	onFeedSelect(feedUrl, feedName);
}

// Lifecycle
onMount(() => {
	loadFeedConfig();
	loadCategories(); // Load categories to get counts
	settings.load();
	
	// Subscribe to settings changes
	const unsubscribe = settings.subscribe((s: { timezone: string; default_view?: 'card' | 'headline' | 'column' }) => {
		selectedTimezone = s.timezone;
		if (s.default_view) {
			selectedDefaultView = s.default_view;
		}
	});
	
	// Cleanup subscription on unmount
	return unsubscribe;
});

// Load keyword filters when category settings modal opens
$effect(() => {
	if (showCategorySettingsModal) {
		loadKeywordFilters();
	}
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
			<Sidebar.Group class="py-0">
				<Sidebar.GroupLabel class="py-1.5 px-0">
				{@const categoryData = categoriesList.find(c => c.name === category)}
				<button
					type="button"
					onclick={() => toggleCategory(category)}
					class="flex w-full items-center justify-between hover:text-foreground group px-2 py-1 rounded {selectedCategory === category ? 'bg-accent' : ''}"
				>
					<div class="flex items-center gap-2 flex-1 min-w-0">
						<ChevronDown
							class="h-4 w-4 transition-transform shrink-0 {expandedCategories.has(category) ? '' : '-rotate-90'}"
						/>
						<span
							onclick={(e) => {
								e.stopPropagation();
								handleCategoryClick(category);
							}}
							class="text-sm font-semibold truncate {selectedCategory === category ? 'text-foreground' : 'text-foreground/90'}"
						>
							{category}
						</span>
					</div>
					{#if categoryData && categoryData.unread_count !== undefined}
						<span class="text-xs text-muted-foreground font-normal shrink-0 ml-auto">
							{categoryData.unread_count}/{categoryData.total_count}
						</span>
					{/if}
				</button>
			</Sidebar.GroupLabel>

					{#if expandedCategories.has(category)}
						<Sidebar.GroupContent>
							<Sidebar.Menu>
								{#each feedConfig[category] as feed}
									<Sidebar.MenuItem>
										<div class="group flex items-center gap-2 px-2 py-1.5 hover:bg-accent/50 rounded transition-colors">
											<Checkbox
												bind:checked={feed.isActive}
												onCheckedChange={saveFeedConfig}
												disabled={isSaving}
												class="shrink-0"
											/>
											<div class="flex items-center gap-2 flex-1 min-w-0">
												<span
													onclick={() => handleFeedClick(feed.url, feed.name)}
													class="cursor-pointer text-sm truncate {selectedFeedUrl === feed.url ? 'font-semibold text-foreground' : (feed.isActive ? 'text-foreground/90' : 'text-muted-foreground line-through')}"
												>
													{feed.name}
												</span>
											</div>
											{#if feed.unread_count !== undefined && feed.unread_count > 0}
												<button
													onclick={(e) => markAllFeedAsRead(feed.url, feed.name, e)}
													class="group/count flex items-center gap-1 px-1.5 py-0.5 rounded hover:bg-accent transition-colors shrink-0 ml-auto"
													title="Mark all as read"
												>
													<span class="text-xs text-muted-foreground group-hover/count:text-foreground font-medium">
														{feed.unread_count}
													</span>
													<Check class="h-3 w-3 text-muted-foreground opacity-0 group-hover/count:opacity-100 transition-opacity" />
												</button>
											{/if}
											<div class="hidden items-center gap-1 group-hover:flex shrink-0">
												<Button
													variant="ghost"
													size="icon"
													class="h-5 w-5 text-muted-foreground hover:text-foreground"
													onclick={() => openEditModal(feed, category)}
												>
													<Pencil class="h-2.5 w-2.5" />
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
					<div class="space-y-1">
						<label class="text-xs font-medium">Polling Interval</label>
						<div class="flex gap-2 items-center">
							<Input
								type="number"
								placeholder="HH"
								bind:value={newFeedPollingHours}
								min="0"
								class="h-8 text-sm flex-1"
							/>
							<span class="text-xs">:</span>
							<Input
								type="number"
								placeholder="MM"
								bind:value={newFeedPollingMinutes}
								min="1"
								class="h-8 text-sm flex-1"
							/>
						</div>
					</div>

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
					<label class="mb-1 block text-sm font-medium">Polling Interval</label>
					<div class="flex gap-2 items-center">
						<Input
							type="number"
							placeholder="HH"
							value={editingFeed ? Math.floor(editingFeed.polling_interval / 60) : 1}
							oninput={(e) => {
								if (editingFeed) {
									const hours = parseInt(e.currentTarget.value) || 0;
									const minutes = editingFeed.polling_interval % 60;
									editingFeed.polling_interval = hours * 60 + minutes;
								}
							}}
							min="0"
							class="flex-1"
						/>
						<span>:</span>
						<Input
							type="number"
							placeholder="MM"
							value={editingFeed ? editingFeed.polling_interval % 60 : 0}
							oninput={(e) => {
								if (editingFeed) {
									const minutes = parseInt(e.currentTarget.value) || 0;
									const hours = Math.floor(editingFeed.polling_interval / 60);
									const totalMinutes = hours * 60 + minutes;
									editingFeed.polling_interval = Math.max(1, totalMinutes);
								}
							}}
							min="0"
							class="flex-1"
						/>
					</div>
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
			<div class="mt-6 flex justify-between gap-2">
				<Button 
					variant="destructive" 
					onclick={() => editingFeed && deleteFeed(editingFeed.id)}
					disabled={isSaving}
				>
					<Trash2 class="mr-2 h-4 w-4" />
					Delete Feed
				</Button>
				<div class="flex gap-2">
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
	</div>
{/if}

<!-- Category Settings Modal -->
<Dialog.Root open={showCategorySettingsModal} onOpenChange={(o) => (showCategorySettingsModal = o)}>
  <Dialog.Content class="max-w-7xl p-0">
    <div class="p-6">
      <h3 class="mb-4 text-lg font-semibold">Settings</h3>
      <Tabs.Root bind:value={activeTab} class="w-full">
<Tabs.List class="grid w-full grid-cols-4">
    <Tabs.Trigger value="categories">Manage Categories</Tabs.Trigger>
    <Tabs.Trigger value="ai-filters">AI Filters</Tabs.Trigger>
    <Tabs.Trigger value="preferences">Preferences</Tabs.Trigger>
    <Tabs.Trigger value="backup">Backup & Export</Tabs.Trigger>
</Tabs.List>
        <Tabs.Content value="categories" class="mt-4 min-h-[400px]">
          <div
            class="mb-4 max-h-[60vh] overflow-y-auto"
            use:dndzone={{ items: categoriesList }}
            onconsider={handleDndConsider}
            onfinalize={handleDndFinalize}
          >
            {#each categoriesList as category (category.id)}
              {@const topicName = `feeds-${category.name.toLowerCase().replace(/\s+/g, '-')}`}
              <div class="mb-3 rounded-md bg-background p-4 border border-border">
                <div class="flex items-center gap-3">
                  <GripVertical class="h-5 w-5 cursor-grab text-muted-foreground flex-shrink-0" />
                  <div class="flex-1 min-w-0">
                    {#if editingCategoryId === category.id}
                      <div class="flex items-center gap-2 mb-1">
                        <Input
                          type="text"
                          bind:value={editingCategoryName}
                          class="h-7 text-sm flex-1"
                          placeholder="Category name"
                        />
                        <Button 
                          size="icon" 
                          class="h-7 w-7" 
                          onclick={() => {
                            updateCategoryName(category.id, editingCategoryName);
                            editingCategoryId = null;
                          }}
                        >
                          <CheckCircle class="h-3 w-3" />
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          class="h-7 w-7" 
                          onclick={() => editingCategoryId = null}
                        >
                          ✕
                        </Button>
                      </div>
                    {:else}
                      <div class="flex items-center gap-2 mb-1">
                        <div class="font-medium text-sm">{category.name}</div>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          class="h-5 w-5" 
                          onclick={() => {
                            editingCategoryId = category.id;
                            editingCategoryName = category.name;
                          }}
                        >
                          <Pencil class="h-3 w-3" />
                        </Button>
                      </div>
                    {/if}
                    <div class="flex items-center gap-2">
                      <span class="text-xs text-muted-foreground font-mono bg-muted px-2 py-0.5 rounded">{topicName}</span>
                      <Button variant="ghost" size="icon" class="h-5 w-5" onclick={() => copyToClipboard(topicName, 'Topic copied to clipboard')}>
                        <Copy class="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                  <div class="flex items-center gap-3 flex-shrink-0 flex-wrap">
                    <div class="flex items-center gap-2">
                      <Bell class="h-4 w-4 text-muted-foreground" />
                      <Switch.Switch checked={category.ntfy_enabled} onCheckedChange={() => toggleCategoryNtfy(category)} />
                      <span class="text-xs text-muted-foreground min-w-[24px]">{category.ntfy_enabled ? 'On' : 'Off'}</span>
                    </div>
									<div class="flex items-center gap-2">
										<SocialIcons network="telegram" alt="" fgColor="#888888" bgColor="transparent" width="24" height="24" />
										<Dialog.Root>
											<Dialog.Trigger>
												<Switch.Switch 
                            checked={category.telegram_enabled}
                            onCheckedChange={() => {
                              if (category.telegram_enabled) {
                                updateCategoryTelegram(category, false, category.telegram_chat_id);
                              } else if (category.telegram_chat_id) {
                                updateCategoryTelegram(category, true, category.telegram_chat_id);
                              }
                            }}
                          />
                        </Dialog.Trigger>
                        <Dialog.Content class="sm:max-w-md">
                          <Dialog.Header>
                            <Dialog.Title>Telegram Notifications - {category.name}</Dialog.Title>
                            <Dialog.Description>
                              Configure Telegram notifications for this category.
                            </Dialog.Description>
                          </Dialog.Header>
                          <div class="space-y-4">
                            <div class="flex items-center gap-2">
                              <Switch.Switch 
                                checked={category.telegram_enabled} 
                                onCheckedChange={(checked) => {
                                  updateCategoryTelegram(category, checked, category.telegram_chat_id);
                                }} 
                              />
                              <span class="text-sm font-medium">Enable Telegram Notifications</span>
                            </div>
                            <div>
                              <label for="telegram-chat-id" class="text-sm font-medium">Chat ID</label>
                              <Input 
                                id="telegram-chat-id" 
                                type="text" 
                                placeholder="Enter your Telegram Chat ID" 
                                value={category.telegram_chat_id || ''}
                                oninput={(e) => {
                                  const chatId = e.currentTarget.value.trim() || null;
                                  category.telegram_chat_id = chatId;
                                }}
                                onblur={() => {
                                  if (category.telegram_enabled && category.telegram_chat_id) {
                                    updateCategoryTelegram(category, true, category.telegram_chat_id);
                                  }
                                }}
                                class="mt-1"
                              />
                              <p class="text-xs text-muted-foreground mt-1">Get your Chat ID from @userinfobot on Telegram</p>
                            </div>
                            <Button 
                              onclick={() => {
                                if (category.telegram_chat_id) {
                                  updateCategoryTelegram(category, true, category.telegram_chat_id);
                                } else {
                                  toast.error('Please enter a Chat ID');
                                }
                              }}
                              class="w-full"
                            >
                              Save Settings
                            </Button>
                          </div>
                        </Dialog.Content>
                      </Dialog.Root>
                      <span class="text-xs text-muted-foreground min-w-[24px]">{category.telegram_enabled ? 'On' : 'Off'}</span>
                    </div>
                    <Button variant={category.is_default ? 'secondary' : 'ghost'} size="sm" class="text-xs whitespace-nowrap" onclick={() => setDefaultCategory(category.id)}>
                      {category.is_default ? 'Default' : 'Set Default'}
                    </Button>
                    <Button variant="ghost" size="icon" class="h-8 w-8" onclick={() => deleteCategory(category.id)}>
                      <Trash2 class="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            {/each}
          </div>
        </Tabs.Content>
        <Tabs.Content value="ai-filters" class="mt-4 min-h-[400px]">
          <div class="w-full">
            <div class="flex gap-2 mb-4 border-b">
              <button type="button" class="px-4 py-2 text-sm font-medium transition-colors {aiFilterSubTab === 'prompt' ? 'border-b-2 border-primary text-foreground' : 'text-muted-foreground hover:text-foreground'}" onclick={() => aiFilterSubTab = 'prompt'}>Prompt-Based Filter</button>
              <button type="button" class="px-4 py-2 text-sm font-medium transition-colors {aiFilterSubTab === 'keywords' ? 'border-b-2 border-primary text-foreground' : 'text-muted-foreground hover:text-foreground'}" onclick={() => aiFilterSubTab = 'keywords'}>Keywords & Topics</button>
            </div>
            {#if aiFilterSubTab === 'prompt'}
              <div class="space-y-4 p-4">
                <div class="space-y-4 max-h-[60vh] overflow-y-auto">
                  {#each categoriesList as category (category.id)}
                    <div class="rounded-lg border border-border bg-background p-4 space-y-3">
                      <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                          <h5 class="font-medium">{category.name}</h5>
                          {#if category.ai_enabled}
                            <span class="text-xs bg-green-500/10 text-green-500 px-2 py-1 rounded">Active</span>
                          {:else}
                            <span class="text-xs bg-muted text-muted-foreground px-2 py-1 rounded">Inactive</span>
                          {/if}
                        </div>
                        <Switch.Switch checked={category.ai_enabled} onCheckedChange={() => toggleCategoryAI(category)} />
                      </div>
                      {#if category.ai_enabled || category.ai_prompt}
                        <div class="space-y-2">
                          <label class="text-xs font-medium text-muted-foreground">Filter Prompt</label>
                          <textarea bind:value={category.ai_prompt} placeholder="e.g., I'm interested in articles about artificial intelligence, machine learning, and software development..." class="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-none" onblur={() => { if (category.ai_prompt !== null && category.ai_prompt.trim() !== '') { saveAIPrompt(category, category.ai_prompt); } }}></textarea>
                          <div class="flex gap-2">
                            <Button size="sm" variant="outline" onclick={() => { if (category.ai_prompt) { saveAIPrompt(category, category.ai_prompt); } }} disabled={!category.ai_prompt || category.ai_prompt.trim() === ''}>Save Prompt</Button>
                            <Button size="sm" variant="secondary" onclick={() => reprocessCategory(category.id)} disabled={!category.ai_enabled || !category.ai_prompt} title="Filter existing articles with current prompt">Reprocess Existing Articles</Button>
                          </div>
                        </div>
                      {:else}
                        <p class="text-xs text-muted-foreground italic">Enable AI filtering to define a custom prompt for this category.</p>
                      {/if}
                    </div>
                  {/each}
                </div>
              </div>
            {:else}
              <div class="space-y-4 p-4">
                <div class="mb-4 flex items-center justify-between">
                  <div>
                    <h4 class="text-sm font-semibold mb-2">Keyword & Topic Filters</h4>
                    <p class="text-sm text-muted-foreground">Define keywords or topics to automatically star and notify.</p>
                  </div>
                  <Button size="sm" onclick={openAddFilterDialog}><Plus class="h-4 w-4 mr-1" />Add Filter</Button>
                </div>
                <div class="space-y-3 max-h-[60vh] overflow-y-auto">
                  {#if keywordFilters.length === 0}
                    <div class="text-center py-8 text-muted-foreground">
                      <p class="text-sm">No filters created yet.</p>
                      <p class="text-xs mt-1">Click "Add Filter" to create your first filter.</p>
                    </div>
                  {:else}
                    {#each keywordFilters as filter (filter.id)}
                      <div class="rounded-lg border border-border bg-background p-4">
                        <div class="flex items-center justify-between gap-3">
                          <div class="flex items-center gap-3 flex-1">
                            <div class="flex-1 min-w-0">
                              <h5 class="font-medium truncate">{filter.name}</h5>
                              <div class="flex items-center gap-2 mt-1">
                                <span class="text-xs px-2 py-0.5 rounded {filter.filter_type === 'keyword' ? 'bg-blue-500/10 text-blue-500' : 'bg-purple-500/10 text-purple-500'}">{filter.filter_type === 'keyword' ? 'Keyword' : 'Topic'}</span>
                                {#if filter.category_name}
                                  <span class="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded truncate">{filter.category_name}</span>
                                {:else}
                                  <span class="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded">Global</span>
                                {/if}
                                {#if filter.enabled}
                                  <span class="text-xs bg-green-500/10 text-green-500 px-2 py-0.5 rounded">Active</span>
                                {:else}
                                  <span class="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded">Inactive</span>
                                {/if}
                              </div>
                            </div>
                          </div>
                          <div class="flex items-center gap-2">
                            <Switch.Switch
                              checked={filter.enabled}
                              onCheckedChange={async (checked) => {
                                try {
                                  const response = await fetch(`/api/filters/${filter.id}`, {
                                    method: 'PUT',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ ...filter, enabled: checked })
                                  });
                                  if (response.ok) {
                                    filter.enabled = checked;
                                    toast.success(checked ? 'Filter enabled' : 'Filter disabled');
                                    await loadKeywordFilters();
                                  } else {
                                    toast.error('Failed to update filter');
                                  }
                                } catch (error) {
                                  toast.error('Failed to update filter');
                                }
                              }}
                              title={filter.enabled ? 'Disable filter' : 'Enable filter'}
                            />
                            <Button variant="outline" size="sm" onclick={() => editFilter(filter)} title="Edit filter"><Pencil class="h-4 w-4 mr-1" />Edit</Button>
                            <Button variant="ghost" size="icon" class="h-8 w-8" onclick={() => deleteKeywordFilter(filter.id)} title="Delete filter"><Trash2 class="h-4 w-4" /></Button>
                          </div>
                        </div>
                      </div>
                    {/each}
                  {/if}
                </div>
              </div>
            {/if}
          </div>
        </Tabs.Content>
<Tabs.Content value="preferences" class="mt-4 min-h-[400px]">
    <div class="space-y-4 p-4">
        <div>
            <h4 class="text-sm font-medium mb-2">Default View Mode</h4>
            <p class="text-sm text-muted-foreground mb-4">Choose how articles are displayed by default when you open the feeds page.</p>
        </div>
        <div class="space-y-2">
            <label class="text-sm font-medium">View Mode</label>
            <Select.Root type="single" bind:value={selectedDefaultView}>
                <Select.Trigger class="w-full">
                    {selectedDefaultView === 'card' ? 'Card View' : selectedDefaultView === 'headline' ? 'Headline View' : 'Column View'}
                </Select.Trigger>
                <Select.Content>
                    <Select.Item value="card" onclick={() => updateDefaultView('card')}>Card View</Select.Item>
                    <Select.Item value="headline" onclick={() => updateDefaultView('headline')}>Headline View</Select.Item>
                    <Select.Item value="column" onclick={() => updateDefaultView('column')}>Column View</Select.Item>
                </Select.Content>
            </Select.Root>
            <p class="text-xs text-muted-foreground mt-2">
                <strong>Card View:</strong> Visual grid with thumbnails and descriptions<br/>
                <strong>Headline View:</strong> Compact list of article titles<br/>
                <strong>Column View:</strong> Split view with article list and content preview
            </p>
        </div>
        <div class="space-y-2">
            <label class="text-sm font-medium">Timezone</label>
            <Select.Root type="single" bind:value={selectedTimezone}>
                <Select.Trigger class="w-full">{selectedTimezone === 'Asia/Kolkata' ? 'IST (Asia/Kolkata)' : 'UTC'}</Select.Trigger>
                <Select.Content>
                    <Select.Item value="Asia/Kolkata" onclick={() => updateTimezone('Asia/Kolkata')}>IST (Asia/Kolkata)</Select.Item>
                    <Select.Item value="UTC" onclick={() => updateTimezone('UTC')}>UTC</Select.Item>
                </Select.Content>
            </Select.Root>
        </div>
    </div>
</Tabs.Content>
        <Tabs.Content value="backup" class="mt-4 min-h-[400px]">
          <div class="space-y-6 p-4">
            <!-- Database Backups Section -->
            <div class="space-y-4">
              <div class="flex items-center justify-between">
                <div>
                  <h4 class="text-sm font-semibold flex items-center gap-2">
                    <Database class="h-4 w-4" />
                    Database Backups
                  </h4>
                  <p class="text-xs text-muted-foreground mt-1">
                    Create and manage full database backups for disaster recovery
                  </p>
                </div>
                <Button onclick={createBackup} disabled={isCreatingBackup} size="sm" class="gap-2">
                  {#if isCreatingBackup}
                    <Loader2 class="h-4 w-4 animate-spin" />
                    Creating...
                  {:else}
                    <Plus class="h-4 w-4" />
                    Create Backup
                  {/if}
                </Button>
              </div>

              {#if activeTab === 'backup'}
                {#if !backups.length && !isLoadingBackups}
                  <div class="rounded-md border border-dashed p-8 text-center">
                    <Database class="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                    <p class="text-sm text-muted-foreground">No backups available</p>
                    <p class="text-xs text-muted-foreground mt-1">Create your first backup to get started</p>
                  </div>
                {:else}
                  <div class="space-y-2 max-h-[200px] overflow-y-auto">
                    {#each backups as backup}
                      <div class="flex items-center justify-between rounded-md border p-3 bg-background">
                        <div class="flex-1 min-w-0">
                          <p class="text-sm font-medium truncate">{backup.filename}</p>
                          <p class="text-xs text-muted-foreground">
                            {new Date(backup.created_at).toLocaleString()} • {backup.size_mb} MB
                          </p>
                        </div>
                        <div class="flex items-center gap-1 ml-2">
                          <Button variant="ghost" size="icon" class="h-8 w-8" onclick={() => downloadBackup(backup.filename)}>
                            <Download class="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" class="h-8 w-8" onclick={() => restoreBackup(backup.filename)} disabled={isRestoringBackup}>
                            <Upload class="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" class="h-8 w-8 text-destructive" onclick={() => deleteBackup(backup.filename)}>
                            <Trash class="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    {/each}
                  </div>
                {/if}
              {/if}
            </div>

            <!-- Data Export Section -->
            <div class="space-y-4 pt-4 border-t">
              <div>
                <h4 class="text-sm font-semibold flex items-center gap-2">
                  <FileDown class="h-4 w-4" />
                  Export Articles
                </h4>
                <p class="text-xs text-muted-foreground mt-1">
                  Download your articles in portable formats
                </p>
              </div>
              <div class="flex gap-2">
                <Button variant="outline" size="sm" onclick={() => exportArticles('csv')} class="gap-2">
                  <FileDown class="h-4 w-4" />
                  Export as CSV
                </Button>
                <Button variant="outline" size="sm" onclick={() => exportArticles('json')} class="gap-2">
                  <FileDown class="h-4 w-4" />
                  Export as JSON
                </Button>
              </div>
            </div>

            <!-- OPML Import/Export Section -->
            <div class="space-y-4 pt-4 border-t">
              <div>
                <h4 class="text-sm font-semibold flex items-center gap-2">
                  <FileText class="h-4 w-4" />
                  OPML Feed Migration
                </h4>
                <p class="text-xs text-muted-foreground mt-1">
                  Import or export your feed subscriptions
                </p>
              </div>
              <div class="flex gap-2">
                <Button variant="outline" size="sm" onclick={exportOPML} class="gap-2">
                  <FileDown class="h-4 w-4" />
                  Export OPML
                </Button>
                <label class="cursor-pointer">
                  <input type="file" accept=".opml,.xml" onchange={importOPML} class="hidden" />
                  <Button
                    variant="outline"
                    size="sm"
                    class="gap-2"
                    onclick={(e) => {
                      e.preventDefault();
                      (e.currentTarget.parentElement?.querySelector('input') as HTMLInputElement)?.click();
                    }}
                  >
                    <FileUp class="h-4 w-4" />
                    Import OPML
                  </Button>
                </label>
              </div>
              <div class="rounded-md bg-muted p-3 text-xs text-muted-foreground">
                <p><strong>Note:</strong> Categorized feeds will be imported into matching categories. Uncategorized feeds will be placed in a "Feeds" category. Duplicate feeds will be skipped.</p>
              </div>
            </div>
          </div>
        </Tabs.Content>
      </Tabs.Root>
      <div class="mt-6 flex justify-end"><Button variant="outline" onclick={closeCategorySettings}>Close</Button></div>
    </div>
    <!-- ... -->
  </Dialog.Content>
</Dialog.Root>

<!-- ... -->
<Dialog.Root open={showFilterDialog} onOpenChange={(o) => (showFilterDialog = o)}>
  <Dialog.Content class="max-w-2xl mx-4 p-6">
    <h3 class="mb-4 text-lg font-semibold">{editingFilter ? 'Edit Filter' : 'Add New Filter'}</h3>
    <div class="space-y-4">
				<!-- Filter Name -->
				<div>
					<label class="text-sm font-medium mb-1 block">Filter Name</label>
					<Input
						type="text"
						bind:value={filterForm.name}
						placeholder="e.g., OpenAI News, Quantum Computing"
					/>
				</div>

				<!-- Filter Type -->
				<div>
					<label class="text-sm font-medium mb-1 block">Filter Type</label>
					<Select.Root
						type="single"
						bind:value={filterForm.filter_type}
					>
						<Select.Trigger class="w-full">
							{filterForm.filter_type === 'keyword' ? 'Keyword (Simple text matching)' : 'Topic (AI-powered semantic matching)'}
						</Select.Trigger>
						<Select.Content>
							<Select.Item value="keyword">Keyword (Simple text matching)</Select.Item>
							<Select.Item value="topic">Topic (AI-powered semantic matching)</Select.Item>
						</Select.Content>
					</Select.Root>
					<p class="text-xs text-muted-foreground mt-1">
						{filterForm.filter_type === 'keyword' 
							? 'Matches exact text in article titles and descriptions' 
							: 'Uses AI to match articles semantically related to your topic'}
					</p>
				</div>

				<!-- Filter Value -->
				<div>
					<label class="text-sm font-medium mb-1 block">
						{filterForm.filter_type === 'keyword' ? 'Keyword' : 'Topic Description'}
					</label>
					{#if filterForm.filter_type === 'keyword'}
						<Input
							type="text"
							bind:value={filterForm.filter_value}
							placeholder="e.g., OpenAI, GPT-4, artificial intelligence"
						/>
						<p class="text-xs text-muted-foreground mt-1">
							Case-insensitive text that will be searched in article content
						</p>
					{:else}
						<textarea
							bind:value={filterForm.filter_value}
							placeholder="e.g., Articles about the impact of quantum computing on cybersecurity and encryption"
							class="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
						></textarea>
						<p class="text-xs text-muted-foreground mt-1">
							Describe the topic you're interested in. Be specific for better AI matching.
						</p>
					{/if}
				</div>

				<!-- Category Selection -->
				<div>
					<label class="text-sm font-medium mb-1 block">Category (Optional)</label>
					<Select.Root
						type="single"
						value={filterForm.category_id?.toString() ?? 'null'}
						onValueChange={(v) => {
							if (v) {
								filterForm.category_id = v === 'null' ? null : parseInt(v, 10);
							} else {
								filterForm.category_id = null;
							}
						}}
					>
						<Select.Trigger class="w-full">
							{filterForm.category_id ? categoriesList.find(c => c.id === filterForm.category_id)?.name ?? 'Select category' : 'Global (All Categories)'}
						</Select.Trigger>
						<Select.Content>
							<Select.Item value="null">Global (All Categories)</Select.Item>
							{#each categoriesList as category}
								<Select.Item value={category.id.toString()}>{category.name}</Select.Item>
							{/each}
						</Select.Content>
					</Select.Root>
					<p class="text-xs text-muted-foreground mt-1">
						Apply this filter globally or to a specific category only
					</p>
				</div>

				<!-- Auto-Star Switch -->
				<div class="flex items-center justify-between rounded-lg border p-4">
					<div class="space-y-0.5">
						<label class="text-sm font-medium cursor-pointer">
							Automatically star matching articles
						</label>
						<p class="text-xs text-muted-foreground">
							Articles that match this filter will be automatically starred
						</p>
					</div>
					<Switch.Switch
						checked={filterForm.auto_star}
						onCheckedChange={(checked) => filterForm.auto_star = checked}
					/>
				</div>

				<!-- Auto-Notify Switch -->
				<div class="flex items-center justify-between rounded-lg border p-4">
					<div class="space-y-0.5">
						<label class="text-sm font-medium cursor-pointer">
							Send ntfy notification with full content
						</label>
						<p class="text-xs text-muted-foreground">
							Get notified with the complete article content when a match is found
						</p>
					</div>
					<Switch.Switch
						checked={filterForm.auto_notify}
						onCheckedChange={(checked) => filterForm.auto_notify = checked}
					/>
				</div>

				<!-- Enabled Switch -->
				<div class="flex items-center justify-between rounded-lg border p-4">
					<div class="space-y-0.5">
						<label class="text-sm font-medium cursor-pointer">
							Enable this filter
						</label>
						<p class="text-xs text-muted-foreground">
							Activate or deactivate this filter without deleting it
						</p>
					</div>
					<Switch.Switch
						checked={filterForm.enabled}
						onCheckedChange={(checked) => filterForm.enabled = checked}
					/>
				</div>
    </div>
    <div class="mt-6 flex justify-end gap-2">
      <Button variant="outline" onclick={() => showFilterDialog = false}>Cancel</Button>
      <Button onclick={saveFilter}>{editingFilter ? 'Update Filter' : 'Create Filter'}</Button>
    </div>
  </Dialog.Content>
</Dialog.Root>
