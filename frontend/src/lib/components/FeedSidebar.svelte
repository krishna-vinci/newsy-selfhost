<script lang="ts">
	import { onMount } from 'svelte';
	import { goto, invalidateAll } from '$app/navigation';
	import { page } from '$app/stores';
	import { toast } from 'svelte-sonner';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import Button from '$lib/components/ui/button/index.svelte';
	import Input from '$lib/components/ui/input/index.svelte';
	import Checkbox from '$lib/components/ui/checkbox/index.svelte';
	import * as Select from '$lib/components/ui/select/index.js';
	import * as Switch from '$lib/components/ui/switch/index.ts';
	import * as Tabs from '$lib/components/ui/tabs/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.ts';
	import TimezonePicker from '$lib/components/TimezonePicker.svelte';
	import {
		ChevronDown,
		Copy,
		Plus,
		Loader2,
		KeyRound,
		Pencil,
		Trash2,
		Settings,
		Send,
		GripVertical,
		FileText,
		Bell,
		Database,
		Download,
		Upload,
		FileDown,
		FileUp,
		Trash,
		CheckCircle,
		Star,
		Check,
		LogOut
	} from '@lucide/svelte';
	import { dndzone } from 'svelte-dnd-action';
	import { settings } from '$lib/stores/settings.ts';

	type Feed = {
		id: number;
		name: string;
		url: string;
		isActive: boolean;
		priority: number;
		retention_days: number | null;
		polling_interval: number;
		fetch_full_content?: boolean;
		unread_count?: number;
	};

	type Category = {
		id: number;
		name: string;
		priority: number;
		is_default: boolean;
		web_push_enabled: boolean;
		telegram_enabled: boolean;
		ai_prompt: string | null;
		ai_enabled: boolean;
		unread_count?: number;
		total_count?: number;
	};

		type NotificationPreferences = {
		telegram: {
			available: boolean;
			enabled: boolean;
			configured: boolean;
			chat_id: string | null;
		};
		web_push: {
			available: boolean;
			configured: boolean;
			subscription_count: number;
			public_key: string | null;
		};
	};

	type ExternalApiConfig = {
		enabled: boolean;
		sse_enabled: boolean;
		public_base_url: string | null;
		endpoints: {
			categories: string;
			feeds: string;
			articles: string;
			article_detail: string;
			stream: string;
		};
		auth: {
			scheme: string;
			token_prefix: string;
			note: string;
		};
	};

	type ApiToken = {
		id: number;
		name: string;
		created_at: string;
		last_used_at: string | null;
		expires_at: string | null;
		revoked_at: string | null;
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

	const sidebar = Sidebar.useSidebar();

	// State
	let feedConfig = $state<FeedConfig>({});
	let isLoading = $state(true);
	let isSaving = $state(false);
	let expandedCategories = $state<Set<string>>(new Set()); // Start collapsed
	let showAddFeedModal = $state(false);

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

	// Notification preferences state
	let notificationPreferences = $state<NotificationPreferences>({
		telegram: {
			available: false,
			enabled: false,
			configured: false,
			chat_id: null
		},
		web_push: {
			available: false,
			configured: false,
			subscription_count: 0,
			public_key: null
		}
	});
	let telegramChatId = $state('');
	let isSavingTelegramPreferences = $state(false);
	let isSendingTelegramTest = $state(false);
	let isUpdatingBrowserPush = $state(false);
	let browserPushSupportMessage = $state<string | null>(null);
	let externalApiConfig = $state<ExternalApiConfig | null>(null);
	let isLoadingExternalApiConfig = $state(false);
	let isSavingExternalApiConfig = $state(false);
	let apiTokens = $state<ApiToken[]>([]);
	let isLoadingApiTokens = $state(false);
	let isCreatingApiToken = $state(false);
	let apiTokenName = $state('');
	let apiTokenExpiryDays = $state('365');
	let latestCreatedApiToken = $state<string | null>(null);
	let latestCreatedApiTokenName = $state<string | null>(null);

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
	let newFeedFetchFullContent = $state(false);
	let isAddingFeed = $state(false);
	let processingFeedId = $state<number | null>(null);

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
	const categoryOptions = $derived(categories.map((cat) => ({ value: cat, label: cat })));

	// Functions
	async function loadFeedConfig() {
		isLoading = true;
		try {
			const response = await fetch(`/api/feeds/config?_=${new Date().getTime()}`);
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

		isAddingFeed = true;
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
					polling_interval: pollingInterval,
					fetch_full_content: newFeedFetchFullContent
				})
			});

			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.error || 'Failed to add feed');
			}

			const result = await response.json();
			processingFeedId = result.feed_id || null;

			toast.success(`Feed added! ${result.articles_added || 0} articles from last 10 days`, {
				description: 'Articles are now available',
				duration: 5000
			});

			resetAddFeedForm();

			// Reload feed config immediately
			await loadFeedConfig();

			// Auto-refresh after 3 seconds to show fetched articles
			setTimeout(async () => {
				await loadFeedConfig();
				processingFeedId = null;
			}, 3000);
		} catch (error) {
			toast.error(error instanceof Error ? error.message : 'Failed to add feed');
			processingFeedId = null;
		} finally {
			isAddingFeed = false;
		}
	}

	function resetAddFeedForm() {
		newFeedUrl = '';
		newFeedName = '';
		selectedCategoryForFeed = '';
		newCategoryName = '';
		useExistingCategory = true;
		showAddFeedModal = false;
		newFeedRetentionDays = undefined;
		newFeedPollingHours = 1;
		newFeedPollingMinutes = 0;
		newFeedFetchFullContent = false;
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
					polling_interval: editingFeed.polling_interval,
					fetch_full_content: editingFeed.fetch_full_content || false
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
		loadNotificationPreferences();
		loadExternalApiConfig();
		loadApiTokens();
		if ($page.data.auth?.isAdmin) {
			loadBackups(); // Load backups when opening settings
		}
		activeTab = 'categories'; // Reset to categories tab
		showCategorySettingsModal = true;
	}

	function closeCategorySettings() {
		latestCreatedApiToken = null;
		latestCreatedApiTokenName = null;
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

	async function loadNotificationPreferences() {
		try {
			const response = await fetch('/api/notifications/preferences');
			if (!response.ok) {
				throw new Error('Failed to load notification preferences');
			}

			const payload = await response.json();
			notificationPreferences = payload;
			telegramChatId = payload.telegram.chat_id || '';
		} catch (error) {
			console.error('Error loading notification preferences:', error);
		}
	}

	async function loadExternalApiConfig() {
		isLoadingExternalApiConfig = true;
		try {
			const response = await fetch('/api/external/config');
			if (!response.ok) {
				throw new Error('Failed to load external API settings');
			}

			externalApiConfig = await response.json();
		} catch (error) {
			console.error('Error loading external API settings:', error);
			toast.error('Failed to load API settings');
		} finally {
			isLoadingExternalApiConfig = false;
		}
	}

	async function saveExternalApiConfig() {
		if (!externalApiConfig) return;

		isSavingExternalApiConfig = true;
		try {
			const response = await fetch('/api/external/config', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					enabled: externalApiConfig.enabled,
					sse_enabled: externalApiConfig.sse_enabled
				})
			});

			if (!response.ok) {
				const error = await response.json().catch(() => null);
				throw new Error(error?.detail || 'Failed to save API settings');
			}

			externalApiConfig = await response.json();
			toast.success('API settings saved');
		} catch (error) {
			toast.error(error instanceof Error ? error.message : 'Failed to save API settings');
			await loadExternalApiConfig();
		} finally {
			isSavingExternalApiConfig = false;
		}
	}

	async function loadApiTokens() {
		isLoadingApiTokens = true;
		try {
			const response = await fetch('/api/auth/api-tokens');
			if (!response.ok) {
				throw new Error('Failed to load API tokens');
			}

			apiTokens = await response.json();
		} catch (error) {
			console.error('Error loading API tokens:', error);
			toast.error('Failed to load API tokens');
		} finally {
			isLoadingApiTokens = false;
		}
	}

	async function createApiToken() {
		if (!apiTokenName.trim()) {
			toast.error('Enter a token name first');
			return;
		}

		const trimmedExpiry = apiTokenExpiryDays.trim();
		const expiresInDays = trimmedExpiry ? Number.parseInt(trimmedExpiry, 10) : null;
		if (
			trimmedExpiry &&
			(expiresInDays === null || Number.isNaN(expiresInDays) || expiresInDays <= 0)
		) {
			toast.error('Expiry must be a positive number of days');
			return;
		}

		isCreatingApiToken = true;
		try {
			const response = await fetch('/api/auth/api-tokens', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: apiTokenName.trim(),
					expires_in_days: expiresInDays || undefined
				})
			});

			const payload = await response.json().catch(() => null);
			if (!response.ok) {
				throw new Error(payload?.detail || 'Failed to create API token');
			}

			latestCreatedApiToken = payload.token || null;
			latestCreatedApiTokenName = payload.name || apiTokenName.trim();
			apiTokenName = '';
			await loadApiTokens();
			toast.success('API token created');
		} catch (error) {
			toast.error(error instanceof Error ? error.message : 'Failed to create API token');
		} finally {
			isCreatingApiToken = false;
		}
	}

	async function revokeApiToken(tokenId: number) {
		if (!confirm('Revoke this API token? Connected applications using it will stop working.')) {
			return;
		}

		try {
			const response = await fetch(`/api/auth/api-tokens/${tokenId}`, {
				method: 'DELETE'
			});
			if (!response.ok) {
				const error = await response.json().catch(() => null);
				throw new Error(error?.detail || 'Failed to revoke API token');
			}

			apiTokens = apiTokens.filter((token) => token.id !== tokenId);
			toast.success('API token revoked');
		} catch (error) {
			toast.error(error instanceof Error ? error.message : 'Failed to revoke API token');
		}
	}

	function getExternalApiBaseUrl(): string {
		if (externalApiConfig?.public_base_url) {
			return externalApiConfig.public_base_url;
		}

		if (typeof window !== 'undefined') {
			return window.location.origin;
		}

		return '';
	}

	function getExternalEndpointUrl(path: string): string {
		const baseUrl = getExternalApiBaseUrl();
		return baseUrl ? `${baseUrl}${path}` : path;
	}

	function formatDateTime(value: string | null): string {
		if (!value) return 'Never';
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) return value;
		return date.toLocaleString();
	}

	async function copyToClipboard(text: string, successMessage: string) {
		try {
			await navigator.clipboard.writeText(text);
			toast.success(successMessage);
		} catch (error) {
			toast.error('Failed to copy to clipboard');
		}
	}

	async function updateCategoryTelegram(category: Category, enabled: boolean) {
		if (enabled && !notificationPreferences.telegram.configured) {
			activeTab = 'notifications';
			toast.error('Set up Telegram in Notifications before enabling category alerts');
			return;
		}

		const previousEnabled = category.telegram_enabled;
		category.telegram_enabled = enabled;

		try {
			const response = await fetch(`/api/category/${category.id}/telegram`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					telegram_enabled: enabled
				})
			});

			if (!response.ok) throw new Error('Failed to update telegram settings');
			toast.success(enabled ? 'Telegram notifications enabled' : 'Telegram notifications disabled');
		} catch (error) {
			category.telegram_enabled = previousEnabled;
			toast.error('Failed to update telegram settings');
		}
	}

	async function updateCategoryWebPush(category: Category, enabled: boolean) {
		const previousEnabled = category.web_push_enabled;
		category.web_push_enabled = enabled;

		try {
			const response = await fetch(`/api/category/${category.id}/web-push`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					web_push_enabled: enabled
				})
			});

			if (!response.ok) throw new Error('Failed to update browser push settings');
			toast.success(
				enabled ? 'Browser push enabled for category' : 'Browser push disabled for category'
			);
		} catch (error) {
			category.web_push_enabled = previousEnabled;
			toast.error('Failed to update browser push settings');
		}
	}

	async function saveTelegramPreferences() {
		if (!notificationPreferences.telegram.available) {
			toast.error('Telegram bot is not configured on this server');
			return;
		}

		if (notificationPreferences.telegram.enabled && !telegramChatId.trim()) {
			toast.error('Enter your Telegram chat ID first');
			return;
		}

		isSavingTelegramPreferences = true;
		try {
			const response = await fetch('/api/notifications/preferences/telegram', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					chat_id: telegramChatId.trim(),
					enabled: notificationPreferences.telegram.enabled
				})
			});

			if (!response.ok) {
				const error = await response.json().catch(() => null);
				throw new Error(error?.detail || 'Failed to save Telegram settings');
			}

			await loadNotificationPreferences();
			toast.success('Telegram settings saved');
		} catch (error) {
			toast.error(error instanceof Error ? error.message : 'Failed to save Telegram settings');
		} finally {
			isSavingTelegramPreferences = false;
		}
	}

	async function sendTelegramTest() {
		if (!notificationPreferences.telegram.configured) {
			toast.error('Save your Telegram chat ID first');
			return;
		}

		isSendingTelegramTest = true;
		try {
			const response = await fetch('/api/notifications/preferences/telegram/test', {
				method: 'POST'
			});
			if (!response.ok) {
				const error = await response.json().catch(() => null);
				throw new Error(error?.detail || 'Failed to send Telegram test');
			}
			toast.success('Telegram test sent');
		} catch (error) {
			toast.error(error instanceof Error ? error.message : 'Failed to send Telegram test');
		} finally {
			isSendingTelegramTest = false;
		}
	}

	function getBrowserPushSupportMessage(): string | null {
		if (typeof window === 'undefined') {
			return null;
		}

		const userAgent = navigator.userAgent || '';
		const isIOS =
			/iPad|iPhone|iPod/.test(userAgent) ||
			(navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
		const isStandalone =
			window.matchMedia?.('(display-mode: standalone)').matches ||
			(window.navigator as Navigator & { standalone?: boolean }).standalone === true;

		if (isIOS && !isStandalone) {
			return 'On iPhone and iPad, browser push only works after adding newsy to the Home Screen from Safari and opening it from the installed app.';
		}

		if (!window.isSecureContext) {
			return 'Browser push requires a secure origin. Use localhost for local testing, or access newsy through an HTTPS URL.';
		}

		if (!('Notification' in window)) {
			return 'This browser does not support the Notifications API required for push alerts.';
		}

		if (!('serviceWorker' in navigator)) {
			return 'This browser does not support service workers required for push alerts.';
		}

		if (!('PushManager' in window)) {
			return 'This browser does not support the Push API required for web push alerts.';
		}

		return null;
	}

	function urlBase64ToUint8Array(base64String: string): Uint8Array {
		const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
		const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
		const rawData = window.atob(base64);
		const outputArray = new Uint8Array(rawData.length);

		for (let i = 0; i < rawData.length; i += 1) {
			outputArray[i] = rawData.charCodeAt(i);
		}

		return outputArray;
	}

	async function getPushSubscription() {
		const supportMessage = getBrowserPushSupportMessage();
		if (supportMessage) {
			browserPushSupportMessage = supportMessage;
			return null;
		}

		let registration = await navigator.serviceWorker.getRegistration();
		if (!registration) {
			registration = await navigator.serviceWorker.register('/service-worker.js');
		}

		await navigator.serviceWorker.ready;
		return registration.pushManager.getSubscription();
	}

	async function enableBrowserPush() {
		if (!notificationPreferences.web_push.available) {
			toast.error('Browser push is not configured on this server');
			return;
		}

		const supportMessage = getBrowserPushSupportMessage();
		if (supportMessage) {
			browserPushSupportMessage = supportMessage;
			toast.error(supportMessage);
			return;
		}

		isUpdatingBrowserPush = true;
		try {
			browserPushSupportMessage = null;
			if (!notificationPreferences.web_push.public_key) {
				throw new Error('Missing VAPID public key');
			}

			const permission = await Notification.requestPermission();
			if (permission !== 'granted') {
				throw new Error('Notification permission was not granted');
			}

			let registration = await navigator.serviceWorker.getRegistration();
			if (!registration) {
				registration = await navigator.serviceWorker.register('/service-worker.js');
			}

			const existingSubscription = await registration.pushManager.getSubscription();
			const subscription =
				existingSubscription ||
				(await registration.pushManager.subscribe({
					userVisibleOnly: true,
					applicationServerKey: urlBase64ToUint8Array(
						notificationPreferences.web_push.public_key || ''
					) as BufferSource
				}));

			const response = await fetch('/api/notifications/push/subscribe', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(subscription)
			});

			if (!response.ok) {
				const error = await response.json().catch(() => null);
				throw new Error(error?.detail || 'Failed to save browser subscription');
			}

			await loadNotificationPreferences();
			toast.success('Browser push enabled');
		} catch (error) {
			toast.error(error instanceof Error ? error.message : 'Failed to enable browser push');
		} finally {
			isUpdatingBrowserPush = false;
		}
	}

	async function disableBrowserPush() {
		const supportMessage = getBrowserPushSupportMessage();
		if (supportMessage) {
			browserPushSupportMessage = supportMessage;
			toast.error(supportMessage);
			return;
		}

		isUpdatingBrowserPush = true;
		try {
			const subscription = await getPushSubscription();
			if (!subscription) {
				await loadNotificationPreferences();
				toast.success('Browser push already disabled');
				return;
			}

			await fetch('/api/notifications/push/unsubscribe', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ endpoint: subscription.endpoint })
			});
			await subscription.unsubscribe();

			await loadNotificationPreferences();
			toast.success('Browser push disabled');
		} catch (error) {
			toast.error(error instanceof Error ? error.message : 'Failed to disable browser push');
		} finally {
			isUpdatingBrowserPush = false;
		}
	}

	async function sendBrowserPushTest() {
		try {
			const response = await fetch('/api/notifications/push/test', {
				method: 'POST'
			});
			if (!response.ok) {
				const error = await response.json().catch(() => null);
				throw new Error(error?.detail || 'Failed to send browser push test');
			}
			toast.success('Browser push test sent');
		} catch (error) {
			toast.error(error instanceof Error ? error.message : 'Failed to send browser push test');
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
			toast.success(
				`Reprocessing complete! ${result.stats.matched} of ${result.stats.total} articles matched`
			);
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
		if (
			!confirm(`WARNING: This will replace your current database with this backup. Are you sure?`)
		)
			return;

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

		// Validate file type
		if (!file.name.endsWith('.opml') && !file.name.endsWith('.xml')) {
			toast.error('Please select an OPML or XML file');
			input.value = '';
			return;
		}

		const formData = new FormData();
		formData.append('file', file);

		try {
			const response = await fetch('/api/opml/import', {
				method: 'POST',
				body: formData
			});

			if (response.ok) {
				const result = await response.json();

				// Build success message
				let message = `Imported ${result.imported} feeds`;
				if (result.skipped > 0) {
					message += ` (${result.skipped} already exist)`;
				}
				if (result.categories_created && result.categories_created.length > 0) {
					message += `, created ${result.categories_created.length} categories`;
				}

				toast.success(message, { duration: 5000 });

				// Show warnings if any
				if (result.warnings && result.warnings.length > 0) {
					toast.warning(
						`Import completed with ${result.warnings.length} warnings. Check console for details.`
					);
					console.warn('OPML import warnings:', result.warnings);
				}

				await loadFeedConfig();
				await loadCategories();
				onconfigchanged();
			} else {
				const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
				toast.error(`Failed to import OPML: ${error.detail || 'Unknown error'}`);
			}
		} catch (error) {
			toast.error('Failed to import OPML. Please check the file format.');
			console.error('OPML import error:', error);
		}

		// Reset input
		input.value = '';
	}

	async function signOut() {
		try {
			await fetch('/api/auth/sign-out', { method: 'POST' });
			if (sidebar.isMobile) {
				sidebar.setOpenMobile(false);
			}
			await invalidateAll();
			await goto('/login');
		} catch (error) {
			toast.error('Failed to log out');
		}
	}

	function handleCategoryClick(category: string) {
		onCategorySelect(category);
		if (sidebar.isMobile) {
			sidebar.setOpenMobile(false);
		}
	}

	function handleFeedClick(feedUrl: string, feedName: string) {
		onFeedSelect(feedUrl, feedName);
		if (sidebar.isMobile) {
			sidebar.setOpenMobile(false);
		}
	}

	// Lifecycle
	onMount(() => {
		loadFeedConfig();
		loadCategories(); // Load categories to get counts
		loadNotificationPreferences();
		browserPushSupportMessage = getBrowserPushSupportMessage();
		settings.load();

		// Subscribe to settings changes
		const unsubscribe = settings.subscribe(
			(s: { timezone: string; default_view?: 'card' | 'headline' | 'column' }) => {
				selectedTimezone = s.timezone;
				if (s.default_view) {
					selectedDefaultView = s.default_view;
				}
			}
		);

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
					<Sidebar.GroupLabel class="px-0 py-1.5">
						{@const categoryData = categoriesList.find((c) => c.name === category)}
						<div
							class="group flex w-full items-center justify-between gap-2 rounded px-2 py-1 hover:text-foreground {selectedCategory ===
							category
								? 'bg-accent'
								: ''}"
						>
							<div class="flex min-w-0 flex-1 items-center gap-2">
								<button
									type="button"
									onclick={() => toggleCategory(category)}
									class="flex h-8 w-8 shrink-0 items-center justify-center rounded hover:bg-accent"
									aria-label={expandedCategories.has(category)
										? `Collapse ${category}`
										: `Expand ${category}`}
								>
									<ChevronDown
										class="h-4 w-4 transition-transform {expandedCategories.has(category)
											? ''
											: '-rotate-90'}"
									/>
								</button>
								<button
									type="button"
									onclick={() => handleCategoryClick(category)}
									class="truncate text-left text-sm font-semibold {selectedCategory === category
										? 'text-foreground'
										: 'text-foreground/90'}"
								>
									{category}
								</button>
							</div>
							{#if categoryData && categoryData.unread_count !== undefined}
								<span class="ml-auto shrink-0 text-xs font-normal text-muted-foreground">
									{categoryData.unread_count}/{categoryData.total_count}
								</span>
							{/if}
						</div>
					</Sidebar.GroupLabel>

					{#if expandedCategories.has(category)}
						<Sidebar.GroupContent>
							<Sidebar.Menu>
								{#each feedConfig[category] as feed}
									<Sidebar.MenuItem>
										<div
											class="group flex items-center gap-2 rounded px-2 py-1.5 transition-colors hover:bg-accent/50"
										>
											<Checkbox
												bind:checked={feed.isActive}
												onCheckedChange={saveFeedConfig}
												disabled={isSaving}
												class="shrink-0"
											/>
											<div class="flex min-w-0 flex-1 items-center gap-2">
												<button
													type="button"
													onclick={() => handleFeedClick(feed.url, feed.name)}
													class="cursor-pointer truncate text-left text-sm {selectedFeedUrl ===
													feed.url
														? 'font-semibold text-foreground'
														: feed.isActive
															? 'text-foreground/90'
															: 'text-muted-foreground line-through'}"
												>
													{feed.name}
												</button>
											</div>
											{#if feed.unread_count !== undefined && feed.unread_count > 0}
												<button
													onclick={(e) => markAllFeedAsRead(feed.url, feed.name, e)}
													class="group/count ml-auto flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 transition-colors hover:bg-accent"
													title="Mark all as read"
												>
													<span
														class="text-xs font-medium text-muted-foreground group-hover/count:text-foreground"
													>
														{feed.unread_count}
													</span>
													<Check
														class="h-3 w-3 text-muted-foreground opacity-0 transition-opacity group-hover/count:opacity-100"
													/>
												</button>
											{/if}
											<div class="hidden shrink-0 items-center gap-1 group-hover:flex">
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

	<!-- Footer with Buttons -->
	<Sidebar.Footer>
		<div class="flex flex-col gap-2">
			<Button
				onclick={() => {
					showAddFeedModal = true;
				}}
				variant="outline"
				size="sm"
				class="w-full"
			>
				<Plus class="mr-2 h-4 w-4" />
				Add Feed
			</Button>
			<Button onclick={openCategorySettings} variant="outline" size="sm" class="w-full">
				<Settings class="mr-2 h-4 w-4" />
				Settings
			</Button>
			{#if $page.data.auth?.user}
				<div
					class="flex items-center gap-2 rounded-md border border-border/60 bg-muted/40 px-3 py-2 text-sm"
				>
					<div class="min-w-0 flex-1 truncate font-medium">{$page.data.auth.user.username}</div>
					<Button
						onclick={signOut}
						variant="ghost"
						size="sm"
						class="h-8 px-2 text-muted-foreground hover:text-foreground"
					>
						<LogOut class="mr-1 h-4 w-4" />
						Logout
					</Button>
				</div>
			{/if}
		</div>
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
		<div
			class="mx-4 max-h-[90vh] w-full max-w-md overflow-y-auto rounded-lg bg-card p-4 shadow-lg sm:p-6"
		>
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
					<Input
						id="edit-feed-url"
						type="url"
						placeholder="Feed URL"
						bind:value={editingFeed.url}
					/>
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
					<div class="flex items-center gap-2">
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
				<div class="flex items-center gap-2">
					<Checkbox bind:checked={editingFeed.fetch_full_content} id="edit-fetch-full-content" />
					<label for="edit-fetch-full-content" class="cursor-pointer text-sm">
						Fetch full article content (slower)
					</label>
				</div>
			</div>
			<div class="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
				<Button
					variant="destructive"
					onclick={() => editingFeed && deleteFeed(editingFeed.id)}
					disabled={isSaving}
					class="w-full sm:w-auto"
				>
					<Trash2 class="mr-2 h-4 w-4" />
					Delete Feed
				</Button>
				<div class="flex flex-col gap-2 sm:flex-row">
					<Button variant="outline" onclick={closeEditModal} class="w-full sm:w-auto">Cancel</Button
					>
					<Button onclick={updateFeed} disabled={isSaving} class="w-full sm:w-auto">
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

<!-- Add Feed Modal -->
<Dialog.Root open={showAddFeedModal} onOpenChange={(o) => (showAddFeedModal = o)}>
	<Dialog.Content class="max-h-[90vh] max-w-[95vw] overflow-y-auto sm:max-w-md">
		<Dialog.Header>
			<Dialog.Title>Add New Feed</Dialog.Title>
			<Dialog.Description>Add a new RSS feed to your collection</Dialog.Description>
		</Dialog.Header>
		<div class="space-y-4 py-4">
			<div class="space-y-2">
				<label class="text-sm font-medium">Feed Name</label>
				<Input type="text" placeholder="Feed name" bind:value={newFeedName} />
			</div>
			<div class="space-y-2">
				<label class="text-sm font-medium">Feed URL</label>
				<Input type="url" placeholder="https://example.com/feed.xml" bind:value={newFeedUrl} />
			</div>
			<div class="space-y-2">
				<label class="text-sm font-medium">Retention Days (Optional)</label>
				<Input type="number" placeholder="30 (default)" bind:value={newFeedRetentionDays} />
			</div>
			<div class="space-y-2">
				<label class="text-sm font-medium">Polling Interval</label>
				<div class="flex items-center gap-2">
					<Input
						type="number"
						placeholder="HH"
						bind:value={newFeedPollingHours}
						min="0"
						class="flex-1"
					/>
					<span class="text-sm">:</span>
					<Input
						type="number"
						placeholder="MM"
						bind:value={newFeedPollingMinutes}
						min="1"
						class="flex-1"
					/>
				</div>
			</div>
			<div class="flex items-center gap-2">
				<Checkbox bind:checked={newFeedFetchFullContent} id="modal-fetch-full-content" />
				<label for="modal-fetch-full-content" class="cursor-pointer text-sm">
					Fetch full article content (slower)
				</label>
			</div>
			<div class="space-y-2">
				<label class="text-sm font-medium">Category</label>
				<div class="mb-2 flex gap-2 text-sm">
					<label class="flex cursor-pointer items-center gap-1">
						<input type="radio" bind:group={useExistingCategory} value={true} class="h-3 w-3" />
						<span>Existing</span>
					</label>
					<label class="flex cursor-pointer items-center gap-1">
						<input type="radio" bind:group={useExistingCategory} value={false} class="h-3 w-3" />
						<span>New</span>
					</label>
				</div>
				{#if useExistingCategory}
					<Select.Root type="single" bind:value={selectedCategoryForFeed}>
						<Select.Trigger>
							{categoryOptions.find((opt) => opt.value === selectedCategoryForFeed)?.label ||
								'Select category'}
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
					<Input type="text" placeholder="New category name" bind:value={newCategoryName} />
				{/if}
			</div>
			{#if processingFeedId}
				<div class="flex items-center gap-2 rounded bg-green-500/10 p-3 text-green-500">
					<CheckCircle class="h-4 w-4" />
					<span class="text-sm">Feed added successfully!</span>
				</div>
			{/if}
		</div>
		<Dialog.Footer>
			<Button variant="outline" onclick={resetAddFeedForm} disabled={isAddingFeed}>Cancel</Button>
			<Button onclick={addCustomFeed} disabled={isAddingFeed}>
				{#if isAddingFeed}
					<Loader2 class="mr-2 h-4 w-4 animate-spin" />
					Processing...
				{:else}
					Add Feed
				{/if}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

<!-- Category Settings Modal -->
<Dialog.Root
	open={showCategorySettingsModal}
	onOpenChange={(open) => {
		if (open) {
			showCategorySettingsModal = true;
		} else {
			closeCategorySettings();
		}
	}}
>
	<Dialog.Content
		class="h-[100dvh] max-h-[100dvh] w-[100vw] max-w-[100vw] overflow-hidden rounded-none p-0 sm:h-[90vh] sm:max-h-[90vh] sm:w-full sm:max-w-2xl sm:rounded-lg lg:max-w-4xl xl:max-w-5xl"
	>
		<div class="flex h-full min-h-0 flex-col">
			<div class="border-b px-4 pt-4 pr-12 pb-3 sm:px-6 sm:pt-6 sm:pb-4">
				<h3 class="text-lg font-semibold">Settings</h3>
				<p class="mt-1 text-xs text-muted-foreground sm:text-sm">
					Categories, alerts, and reading preferences in one place.
				</p>
			</div>
			<Tabs.Root bind:value={activeTab} class="flex min-h-0 flex-1 flex-col">
			<Tabs.List
				class="-mx-0 flex h-auto w-full snap-x snap-mandatory justify-start gap-2 overflow-x-auto rounded-none border-b bg-transparent px-4 py-3 sm:mx-6 sm:mt-4 sm:grid sm:grid-cols-6 sm:gap-0 sm:overflow-visible sm:rounded-lg sm:border-0 sm:bg-muted sm:p-[3px]"
			>
					<Tabs.Trigger
						value="categories"
						class="h-9 min-w-max shrink-0 snap-start px-3 text-xs sm:text-sm"
						><span class="sm:hidden">Categories</span><span class="hidden sm:inline"
							>Manage Categories</span
						></Tabs.Trigger
					>
					<Tabs.Trigger
						value="ai-filters"
						class="h-9 min-w-max shrink-0 snap-start px-3 text-xs sm:text-sm"
						><span class="sm:hidden">Filters</span><span class="hidden sm:inline">AI Filters</span
						></Tabs.Trigger
					>
					<Tabs.Trigger
						value="preferences"
						class="h-9 min-w-max shrink-0 snap-start px-3 text-xs sm:text-sm"
						><span class="sm:hidden">View</span><span class="hidden sm:inline">Preferences</span
						></Tabs.Trigger
					>
					<Tabs.Trigger
						value="notifications"
						class="h-9 min-w-max shrink-0 snap-start px-3 text-xs sm:text-sm"
						><span class="sm:hidden">Alerts</span><span class="hidden sm:inline">Notifications</span
						></Tabs.Trigger
					>
					<Tabs.Trigger
						value="api"
						class="h-9 min-w-max shrink-0 snap-start px-3 text-xs sm:text-sm"
						><span class="sm:hidden">API</span><span class="hidden sm:inline">External API</span
						></Tabs.Trigger
					>
					<Tabs.Trigger
						value="backup"
						class="h-9 min-w-max shrink-0 snap-start px-3 text-xs sm:text-sm"
						><span class="sm:hidden">Export</span><span class="hidden sm:inline"
							>{$page.data.auth?.isAdmin ? 'Backup & Export' : 'Data Export'}</span
						></Tabs.Trigger
					>
				</Tabs.List>
				<Tabs.Content value="categories" class="mt-0 min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
					<div
						class="max-h-full overflow-y-auto"
						use:dndzone={{ items: categoriesList }}
						onconsider={handleDndConsider}
						onfinalize={handleDndFinalize}
					>
						{#each categoriesList as category (category.id)}
							<div class="mb-3 rounded-md border border-border bg-background p-3 sm:p-4">
								<div class="flex flex-col gap-3 sm:flex-row sm:items-center">
									<GripVertical class="h-5 w-5 flex-shrink-0 cursor-grab text-muted-foreground" />
									<div class="min-w-0 flex-1">
										{#if editingCategoryId === category.id}
											<div class="mb-1 flex items-center gap-2">
												<Input
													type="text"
													bind:value={editingCategoryName}
													class="h-7 flex-1 text-sm"
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
													onclick={() => (editingCategoryId = null)}
												>
													✕
												</Button>
											</div>
										{:else}
											<div class="mb-1 flex items-center gap-2">
												<div class="text-sm font-medium">{category.name}</div>
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
									</div>
									<div class="flex flex-wrap items-center gap-2 sm:justify-end sm:gap-3">
										<div
											class="flex items-center gap-2 rounded-md border px-3 py-2"
											title="Push notifications"
										>
											<Bell class="h-4 w-4 text-muted-foreground" />
											<Switch.Switch
												checked={category.web_push_enabled}
												onCheckedChange={(checked) => {
													updateCategoryWebPush(category, checked);
												}}
											/>
											<span class="min-w-[24px] text-xs text-muted-foreground"
												>{category.web_push_enabled ? 'On' : 'Off'}</span
											>
										</div>
										<div
											class="flex items-center gap-2 rounded-md border px-3 py-2"
											title="Telegram notifications"
										>
											<Send class="h-4 w-4 text-muted-foreground" />
											<Switch.Switch
												checked={category.telegram_enabled}
												onCheckedChange={(checked) => {
													updateCategoryTelegram(category, checked);
												}}
											/>
											<span class="min-w-[24px] text-xs text-muted-foreground"
												>{category.telegram_enabled ? 'On' : 'Off'}</span
											>
										</div>
										<Button
											variant={category.is_default ? 'secondary' : 'ghost'}
											size="sm"
											class="text-xs whitespace-nowrap"
											onclick={() => setDefaultCategory(category.id)}
										>
											{category.is_default ? 'Default' : 'Set Default'}
										</Button>
										<Button
											variant="ghost"
											size="icon"
											class="h-8 w-8"
											onclick={() => deleteCategory(category.id)}
										>
											<Trash2 class="h-4 w-4" />
										</Button>
									</div>
								</div>
							</div>
						{/each}
					</div>
				</Tabs.Content>
				<Tabs.Content value="ai-filters" class="mt-0 min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
					<div class="w-full">
						<div class="mb-4 flex gap-2 border-b">
							<button
								type="button"
								class="px-4 py-2 text-sm font-medium transition-colors {aiFilterSubTab === 'prompt'
									? 'border-b-2 border-primary text-foreground'
									: 'text-muted-foreground hover:text-foreground'}"
								onclick={() => (aiFilterSubTab = 'prompt')}>Prompt-Based Filter</button
							>
							<button
								type="button"
								class="px-4 py-2 text-sm font-medium transition-colors {aiFilterSubTab ===
								'keywords'
									? 'border-b-2 border-primary text-foreground'
									: 'text-muted-foreground hover:text-foreground'}"
								onclick={() => (aiFilterSubTab = 'keywords')}>Keywords & Topics</button
							>
						</div>
						{#if aiFilterSubTab === 'prompt'}
							<div class="space-y-4 p-4">
								<p class="mb-2 text-sm text-muted-foreground">
									Enable AI filtering to define a custom prompt for each category.
								</p>
								<div class="max-h-[50vh] space-y-4 overflow-y-auto sm:max-h-[60vh]">
									{#each categoriesList as category (category.id)}
										<div class="space-y-3 rounded-lg border border-border bg-background p-4">
											<div class="flex items-center justify-between">
												<div class="flex items-center gap-3">
													<h5 class="font-medium">{category.name}</h5>
													{#if category.ai_enabled}
														<span class="rounded bg-green-500/10 px-2 py-1 text-xs text-green-500"
															>Active</span
														>
													{:else}
														<span class="rounded bg-muted px-2 py-1 text-xs text-muted-foreground"
															>Inactive</span
														>
													{/if}
												</div>
												<Switch.Switch
													checked={category.ai_enabled}
													onCheckedChange={() => toggleCategoryAI(category)}
												/>
											</div>
											{#if category.ai_enabled || category.ai_prompt}
												<div class="space-y-2">
													<label class="text-xs font-medium text-muted-foreground"
														>Filter Prompt</label
													>
													<textarea
														bind:value={category.ai_prompt}
														placeholder="e.g., I'm interested in articles about artificial intelligence, machine learning, and software development..."
														class="min-h-[80px] w-full resize-none rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
														onblur={() => {
															if (category.ai_prompt !== null && category.ai_prompt.trim() !== '') {
																saveAIPrompt(category, category.ai_prompt);
															}
														}}
													></textarea>
													<div class="flex gap-2">
														<Button
															size="sm"
															variant="outline"
															onclick={() => {
																if (category.ai_prompt) {
																	saveAIPrompt(category, category.ai_prompt);
																}
															}}
															disabled={!category.ai_prompt || category.ai_prompt.trim() === ''}
															>Save Prompt</Button
														>
														<Button
															size="sm"
															variant="secondary"
															onclick={() => reprocessCategory(category.id)}
															disabled={!category.ai_enabled || !category.ai_prompt}
															title="Filter existing articles with current prompt"
															>Reprocess Existing Articles</Button
														>
													</div>
												</div>
											{/if}
										</div>
									{/each}
								</div>
							</div>
						{:else}
							<div class="space-y-4 p-4">
								<div class="mb-4 flex items-center justify-between">
									<div>
										<h4 class="mb-2 text-sm font-semibold">Keyword & Topic Filters</h4>
										<p class="text-sm text-muted-foreground">
											Define keywords or topics to automatically star and notify.
										</p>
									</div>
									<Button size="sm" onclick={openAddFilterDialog}
										><Plus class="mr-1 h-4 w-4" />Add Filter</Button
									>
								</div>
								<div class="max-h-[60vh] space-y-3 overflow-y-auto">
									{#if keywordFilters.length === 0}
										<div class="py-8 text-center text-muted-foreground">
											<p class="text-sm">No filters created yet.</p>
											<p class="mt-1 text-xs">Click "Add Filter" to create your first filter.</p>
										</div>
									{:else}
										{#each keywordFilters as filter (filter.id)}
											<div class="rounded-lg border border-border bg-background p-4">
												<div class="flex items-center justify-between gap-3">
													<div class="flex flex-1 items-center gap-3">
														<div class="min-w-0 flex-1">
															<h5 class="truncate font-medium">{filter.name}</h5>
															<div class="mt-1 flex items-center gap-2">
																<span
																	class="rounded px-2 py-0.5 text-xs {filter.filter_type ===
																	'keyword'
																		? 'bg-blue-500/10 text-blue-500'
																		: 'bg-purple-500/10 text-purple-500'}"
																	>{filter.filter_type === 'keyword' ? 'Keyword' : 'Topic'}</span
																>
																{#if filter.category_name}
																	<span
																		class="truncate rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground"
																		>{filter.category_name}</span
																	>
																{:else}
																	<span
																		class="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground"
																		>Global</span
																	>
																{/if}
																{#if filter.enabled}
																	<span
																		class="rounded bg-green-500/10 px-2 py-0.5 text-xs text-green-500"
																		>Active</span
																	>
																{:else}
																	<span
																		class="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground"
																		>Inactive</span
																	>
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
														<Button
															variant="outline"
															size="sm"
															onclick={() => editFilter(filter)}
															title="Edit filter"><Pencil class="mr-1 h-4 w-4" />Edit</Button
														>
														<Button
															variant="ghost"
															size="icon"
															class="h-8 w-8"
															onclick={() => deleteKeywordFilter(filter.id)}
															title="Delete filter"><Trash2 class="h-4 w-4" /></Button
														>
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
				<Tabs.Content value="preferences" class="mt-0 min-h-0 flex-1 overflow-y-auto">
					<div class="space-y-4 p-4 sm:p-5">
						<div>
							<h4 class="mb-2 text-sm font-medium">Default View Mode</h4>
							<p class="text-xs text-muted-foreground sm:text-sm">
								Choose the layout used when you open the feeds page.
							</p>
						</div>
						<div class="space-y-2">
							<label class="text-sm font-medium">View Mode</label>
							<Select.Root type="single" bind:value={selectedDefaultView}>
								<Select.Trigger class="w-full">
									{selectedDefaultView === 'card'
										? 'Card View'
										: selectedDefaultView === 'headline'
											? 'Headline View'
											: 'Column View'}
								</Select.Trigger>
								<Select.Content>
									<Select.Item value="card" onclick={() => updateDefaultView('card')}
										>Card View</Select.Item
									>
									<Select.Item value="headline" onclick={() => updateDefaultView('headline')}
										>Headline View</Select.Item
									>
									<Select.Item value="column" onclick={() => updateDefaultView('column')}
										>Column View</Select.Item
									>
								</Select.Content>
							</Select.Root>
							<div class="mt-2 rounded-md bg-muted p-3 text-xs text-muted-foreground">
								Card shows more detail, Headline is compact, and Column opens a split view on larger
								screens.
							</div>
						</div>
					<div class="space-y-2">
						<TimezonePicker
							id="settings-timezone-search"
							value={selectedTimezone}
							onChange={(timezone) => {
								selectedTimezone = timezone;
								updateTimezone(timezone);
							}}
							description="Search by country, city, or timezone name."
						/>
					</div>
				</div>
				</Tabs.Content>
				<Tabs.Content value="notifications" class="mt-0 min-h-0 flex-1 overflow-y-auto">
					<div class="space-y-4 p-4 sm:p-5">
						<div class="rounded-lg border bg-background p-3 sm:p-4">
							<div class="mb-3">
								<h4 class="text-sm font-semibold">In-app inbox</h4>
								<p class="mt-1 text-xs text-muted-foreground">
									Use the header bell to review alerts and delivery updates.
								</p>
							</div>
							<div class="rounded-md bg-muted p-3 text-xs text-muted-foreground">
								In-app alerts always work and need no extra setup.
							</div>
							<p class="mt-3 text-xs text-muted-foreground">
								Push and Telegram both respect the category toggles in <strong
									>Manage Categories</strong
								>.
							</p>
						</div>

						<div class="rounded-lg border bg-background p-3 sm:p-4">
							<div
								class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4"
							>
								<div>
									<h4 class="text-sm font-semibold">Telegram</h4>
									<p class="mt-1 text-xs text-muted-foreground">
										Connect one Telegram chat, then enable it per category.
									</p>
								</div>
								<Switch.Switch
									checked={notificationPreferences.telegram.enabled}
									disabled={!notificationPreferences.telegram.available}
									onCheckedChange={(checked) => {
										notificationPreferences.telegram.enabled = checked;
									}}
								/>
							</div>

							{#if notificationPreferences.telegram.available}
								<div class="space-y-3">
									<div>
										<label for="global-telegram-chat-id" class="mb-1 block text-sm font-medium"
											>Chat ID</label
										>
										<Input
											id="global-telegram-chat-id"
											type="text"
											bind:value={telegramChatId}
											placeholder="Enter your Telegram chat ID"
										/>
										<p class="mt-1 text-xs text-muted-foreground">
											Start your bot first, then paste the chat ID here.
										</p>
									</div>
									<div class="flex flex-wrap gap-2">
										<Button
											onclick={saveTelegramPreferences}
											disabled={isSavingTelegramPreferences}
										>
											{#if isSavingTelegramPreferences}
												<Loader2 class="mr-2 h-4 w-4 animate-spin" />
											{/if}
											Save Telegram
										</Button>
										<Button
											variant="outline"
											onclick={sendTelegramTest}
											disabled={isSendingTelegramTest ||
												!notificationPreferences.telegram.configured}
										>
											{#if isSendingTelegramTest}
												<Loader2 class="mr-2 h-4 w-4 animate-spin" />
											{/if}
											Send test
										</Button>
									</div>
								</div>
							{:else}
								<p class="text-xs text-muted-foreground">
									Telegram is unavailable until the server has a bot token configured.
								</p>
							{/if}
						</div>

						<div class="rounded-lg border bg-background p-3 sm:p-4">
							<div class="mb-3">
								<h4 class="text-sm font-semibold">Browser push</h4>
								<p class="mt-1 text-xs text-muted-foreground">
									Enable browser alerts on this device.
								</p>
							</div>
							{#if notificationPreferences.web_push.available}
								<div class="space-y-3">
									{#if browserPushSupportMessage}
										<div
											class="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs leading-relaxed text-muted-foreground"
										>
											{browserPushSupportMessage}
										</div>
									{/if}
									<p class="text-xs text-muted-foreground">
										{#if notificationPreferences.web_push.configured}
											{notificationPreferences.web_push.subscription_count} browser subscription{notificationPreferences
												.web_push.subscription_count === 1
												? ''
												: 's'} active for this account.
										{:else}
											No browser subscription is active yet for this account.
										{/if}
									</p>
									<div class="flex flex-wrap gap-2">
										<Button
											onclick={enableBrowserPush}
											disabled={isUpdatingBrowserPush || !!browserPushSupportMessage}
										>
											{#if isUpdatingBrowserPush}
												<Loader2 class="mr-2 h-4 w-4 animate-spin" />
											{/if}
											Enable on this device
										</Button>
										<Button
											variant="outline"
											onclick={disableBrowserPush}
											disabled={isUpdatingBrowserPush ||
												!notificationPreferences.web_push.configured}
										>
											Disable on this device
										</Button>
										<Button
											variant="outline"
											onclick={sendBrowserPushTest}
											disabled={!notificationPreferences.web_push.configured}
										>
											Send test
										</Button>
									</div>
								</div>
							{:else}
								<p class="text-xs text-muted-foreground">
									Browser push is unavailable until VAPID keys are configured on the server.
								</p>
							{/if}
						</div>
					</div>
				</Tabs.Content>
				<Tabs.Content value="api" class="mt-0 min-h-0 flex-1 overflow-y-auto">
					<div class="space-y-4 p-4 sm:p-5">
						{#if isLoadingExternalApiConfig && !externalApiConfig}
							<div class="flex items-center justify-center py-12 text-sm text-muted-foreground">
								<Loader2 class="mr-2 h-4 w-4 animate-spin" />
								Loading API settings…
							</div>
						{:else if externalApiConfig}
							<div class="rounded-lg border bg-background p-3 sm:p-4">
								<div
									class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4"
								>
									<div>
										<h4 class="text-sm font-semibold">Dedicated external API</h4>
										<p class="mt-1 text-xs text-muted-foreground">
											Expose your feeds to other applications over REST and SSE using API tokens.
										</p>
									</div>
									<Switch.Switch
										checked={externalApiConfig.enabled}
										onCheckedChange={(checked) => {
											if (!externalApiConfig) return;
											externalApiConfig = {
												enabled: checked,
												sse_enabled: checked ? externalApiConfig.sse_enabled : false,
												public_base_url: externalApiConfig.public_base_url,
												endpoints: externalApiConfig.endpoints,
												auth: externalApiConfig.auth
											};
										}}
									/>
								</div>

								<div class="space-y-3">
									<div class="rounded-md border p-3">
										<div class="flex items-center justify-between gap-3">
											<div>
												<p class="text-sm font-medium">Server-Sent Events</p>
												<p class="mt-1 text-xs text-muted-foreground">
													Use the stream endpoint for new article and notification events.
												</p>
											</div>
											<Switch.Switch
												checked={externalApiConfig.sse_enabled}
												disabled={!externalApiConfig.enabled}
												onCheckedChange={(checked) => {
													if (!externalApiConfig) return;
													externalApiConfig = {
														enabled: externalApiConfig.enabled,
														sse_enabled: checked,
														public_base_url: externalApiConfig.public_base_url,
														endpoints: externalApiConfig.endpoints,
														auth: externalApiConfig.auth
													};
												}}
											/>
										</div>
									</div>

									<div class="flex flex-wrap gap-2">
										<Button onclick={saveExternalApiConfig} disabled={isSavingExternalApiConfig}>
											{#if isSavingExternalApiConfig}
												<Loader2 class="mr-2 h-4 w-4 animate-spin" />
											{/if}
											Save API settings
										</Button>
										{#if !externalApiConfig.enabled}
											<p class="self-center text-xs text-muted-foreground">
												External clients cannot access the dedicated API until it is enabled.
											</p>
										{/if}
									</div>
								</div>
							</div>

							<div class="rounded-lg border bg-background p-3 sm:p-4">
								<div class="mb-3">
									<h4 class="text-sm font-semibold">Connection details</h4>
									<p class="mt-1 text-xs text-muted-foreground">
										Use these endpoints from scripts, bots, or trading systems. The stream endpoint uses
										SSE and still requires a Bearer token header.
									</p>
								</div>

								<div class="space-y-2 text-xs text-muted-foreground">
									<p><strong>Base URL:</strong> {getExternalApiBaseUrl() || 'Set PUBLIC_URL or use the current site origin.'}</p>
									<p><strong>REST:</strong> {getExternalEndpointUrl(externalApiConfig.endpoints.articles)}</p>
									<p><strong>SSE:</strong> {getExternalEndpointUrl(externalApiConfig.endpoints.stream)}</p>
								</div>

								<div class="mt-4 grid gap-3 lg:grid-cols-2">
									<div>
										<p class="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
											Fetch articles
										</p>
										<pre class="overflow-x-auto rounded-md bg-muted p-3 text-xs">{`curl -H "Authorization: Bearer <token>" "${getExternalEndpointUrl(externalApiConfig.endpoints.articles)}?limit=25"`}</pre>
									</div>
									<div>
										<p class="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
											Open SSE stream
										</p>
										<pre class="overflow-x-auto rounded-md bg-muted p-3 text-xs">{`curl -N -H "Authorization: Bearer <token>" "${getExternalEndpointUrl(externalApiConfig.endpoints.stream)}"`}</pre>
									</div>
								</div>
							</div>

							<div class="rounded-lg border bg-background p-3 sm:p-4">
								<div class="mb-4 flex items-start gap-3">
									<KeyRound class="mt-0.5 h-4 w-4 text-muted-foreground" />
									<div>
										<h4 class="text-sm font-semibold">API tokens</h4>
										<p class="mt-1 text-xs text-muted-foreground">
											Generate a token for each external application. Tokens are shown only once when
											created.
										</p>
									</div>
								</div>

								<div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_160px_auto]">
									<div class="space-y-1.5">
										<label for="api-token-name" class="text-sm font-medium">Token name</label>
										<Input
											id="api-token-name"
											bind:value={apiTokenName}
											placeholder="e.g. trading-bot-prod"
										/>
									</div>
									<div class="space-y-1.5">
										<label for="api-token-expiry" class="text-sm font-medium">Expiry days</label>
										<Input
											id="api-token-expiry"
											type="number"
											min="1"
											bind:value={apiTokenExpiryDays}
											placeholder="365"
										/>
									</div>
									<div class="sm:self-end">
										<Button onclick={createApiToken} disabled={isCreatingApiToken} class="w-full sm:w-auto">
											{#if isCreatingApiToken}
												<Loader2 class="mr-2 h-4 w-4 animate-spin" />
											{/if}
											Generate token
										</Button>
									</div>
								</div>

								{#if latestCreatedApiToken}
									<div class="mt-4 rounded-md border border-green-500/30 bg-green-500/10 p-3">
										<p class="text-sm font-medium">Copy your new token now</p>
										<p class="mt-1 text-xs text-muted-foreground">
											{latestCreatedApiTokenName || 'New token'} will not be shown again after you close this dialog.
										</p>
										<div class="mt-3 flex flex-col gap-2 sm:flex-row">
											<Input value={latestCreatedApiToken} readonly class="font-mono text-xs" />
											<Button
												variant="outline"
												onclick={() => copyToClipboard(latestCreatedApiToken || '', 'API token copied')}
											>
												<Copy class="mr-2 h-4 w-4" />
												Copy
											</Button>
										</div>
									</div>
								{/if}

								<div class="mt-4 space-y-2">
									{#if isLoadingApiTokens}
										<div class="flex items-center justify-center py-8 text-sm text-muted-foreground">
											<Loader2 class="mr-2 h-4 w-4 animate-spin" />
											Loading tokens…
										</div>
									{:else if !apiTokens.length}
										<div class="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
											No API tokens yet.
										</div>
									{:else}
										{#each apiTokens as token (token.id)}
											<div class="rounded-md border p-3">
												<div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
													<div class="min-w-0 flex-1">
														<p class="truncate text-sm font-medium">{token.name}</p>
														<p class="mt-1 text-xs text-muted-foreground">
															Created {formatDateTime(token.created_at)}
															{#if token.last_used_at}
																• Last used {formatDateTime(token.last_used_at)}
															{/if}
															{#if token.expires_at}
																• Expires {formatDateTime(token.expires_at)}
															{/if}
															{#if token.revoked_at}
																• Revoked {formatDateTime(token.revoked_at)}
															{/if}
														</p>
													</div>
													<Button variant="outline" size="sm" onclick={() => revokeApiToken(token.id)}>
														Revoke
													</Button>
												</div>
											</div>
										{/each}
									{/if}
								</div>
							</div>
						{:else}
							<div class="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
								Unable to load API settings.
							</div>
						{/if}
					</div>
				</Tabs.Content>
				<Tabs.Content value="backup" class="mt-0 min-h-0 flex-1 overflow-y-auto">
					<div class="space-y-5 p-4 sm:p-5">
						{#if $page.data.auth?.isAdmin}
							<!-- Database Backups Section -->
							<div class="space-y-4">
								<div class="flex items-center justify-between">
									<div>
										<h4 class="flex items-center gap-2 text-sm font-semibold">
											<Database class="h-4 w-4" />
											Database Backups
										</h4>
										<p class="mt-1 text-xs text-muted-foreground">
											Create and manage full database backups for disaster recovery
										</p>
									</div>
									<Button
										onclick={createBackup}
										disabled={isCreatingBackup}
										size="sm"
										class="gap-2"
									>
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
											<Database class="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
											<p class="text-sm text-muted-foreground">No backups available</p>
											<p class="mt-1 text-xs text-muted-foreground">
												Create your first backup to get started
											</p>
										</div>
									{:else}
										<div class="max-h-[200px] space-y-2 overflow-y-auto">
											{#each backups as backup}
												<div
													class="flex items-center justify-between rounded-md border bg-background p-3"
												>
													<div class="min-w-0 flex-1">
														<p class="truncate text-sm font-medium">{backup.filename}</p>
														<p class="text-xs text-muted-foreground">
															{new Date(backup.created_at).toLocaleString()} • {backup.size_mb} MB
														</p>
													</div>
													<div class="ml-2 flex items-center gap-1">
														<Button
															variant="ghost"
															size="icon"
															class="h-8 w-8"
															onclick={() => downloadBackup(backup.filename)}
														>
															<Download class="h-4 w-4" />
														</Button>
														<Button
															variant="ghost"
															size="icon"
															class="h-8 w-8"
															onclick={() => restoreBackup(backup.filename)}
															disabled={isRestoringBackup}
														>
															<Upload class="h-4 w-4" />
														</Button>
														<Button
															variant="ghost"
															size="icon"
															class="h-8 w-8 text-destructive"
															onclick={() => deleteBackup(backup.filename)}
														>
															<Trash class="h-4 w-4" />
														</Button>
													</div>
												</div>
											{/each}
										</div>
									{/if}
								{/if}
							</div>
						{/if}

						<!-- Data Export Section -->
						<div class="space-y-4 border-t pt-4">
							<div>
								<h4 class="flex items-center gap-2 text-sm font-semibold">
									<FileDown class="h-4 w-4" />
									Export Articles
								</h4>
								<p class="mt-1 text-xs text-muted-foreground">
									Download your articles in portable formats
								</p>
							</div>
							<div class="flex flex-wrap gap-2">
								<Button
									variant="outline"
									size="sm"
									onclick={() => exportArticles('csv')}
									class="gap-2"
								>
									<FileDown class="h-4 w-4" />
									Export as CSV
								</Button>
								<Button
									variant="outline"
									size="sm"
									onclick={() => exportArticles('json')}
									class="gap-2"
								>
									<FileDown class="h-4 w-4" />
									Export as JSON
								</Button>
							</div>
						</div>

						<!-- OPML Import/Export Section -->
						<div class="space-y-4 border-t pt-4">
							<div>
								<h4 class="flex items-center gap-2 text-sm font-semibold">
									<FileText class="h-4 w-4" />
									OPML Feed Migration
								</h4>
								<p class="mt-1 text-xs text-muted-foreground">
									Import or export your feed subscriptions
								</p>
							</div>
							<div class="flex flex-wrap gap-2">
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
											(
												e.currentTarget.parentElement?.querySelector('input') as HTMLInputElement
											)?.click();
										}}
									>
										<FileUp class="h-4 w-4" />
										Import OPML
									</Button>
								</label>
							</div>
							<div class="rounded-md bg-muted p-3 text-xs text-muted-foreground">
								<p>
									<strong>Note:</strong> Categorized feeds will be imported into matching categories.
									Uncategorized feeds will be placed in a "Feeds" category. Duplicate feeds will be skipped.
								</p>
							</div>
						</div>
					</div>
				</Tabs.Content>
			</Tabs.Root>
			<div class="border-t px-4 py-3 sm:px-6">
				<div class="flex justify-end">
					<Button variant="outline" onclick={closeCategorySettings}>Close</Button>
				</div>
			</div>
		</div>
		<!-- ... -->
	</Dialog.Content>
</Dialog.Root>

<!-- ... -->
<Dialog.Root open={showFilterDialog} onOpenChange={(o) => (showFilterDialog = o)}>
	<Dialog.Content class="mx-4 max-w-2xl p-6">
		<h3 class="mb-4 text-lg font-semibold">{editingFilter ? 'Edit Filter' : 'Add New Filter'}</h3>
		<div class="space-y-4">
			<!-- Filter Name -->
			<div>
				<label class="mb-1 block text-sm font-medium">Filter Name</label>
				<Input
					type="text"
					bind:value={filterForm.name}
					placeholder="e.g., OpenAI News, Quantum Computing"
				/>
			</div>

			<!-- Filter Type -->
			<div>
				<label class="mb-1 block text-sm font-medium">Filter Type</label>
				<Select.Root type="single" bind:value={filterForm.filter_type}>
					<Select.Trigger class="w-full">
						{filterForm.filter_type === 'keyword'
							? 'Keyword (Simple text matching)'
							: 'Topic (AI-powered semantic matching)'}
					</Select.Trigger>
					<Select.Content>
						<Select.Item value="keyword">Keyword (Simple text matching)</Select.Item>
						<Select.Item value="topic">Topic (AI-powered semantic matching)</Select.Item>
					</Select.Content>
				</Select.Root>
				<p class="mt-1 text-xs text-muted-foreground">
					{filterForm.filter_type === 'keyword'
						? 'Matches exact text in article titles and descriptions'
						: 'Uses AI to match articles semantically related to your topic'}
				</p>
			</div>

			<!-- Filter Value -->
			<div>
				<label class="mb-1 block text-sm font-medium">
					{filterForm.filter_type === 'keyword' ? 'Keyword' : 'Topic Description'}
				</label>
				{#if filterForm.filter_type === 'keyword'}
					<Input
						type="text"
						bind:value={filterForm.filter_value}
						placeholder="e.g., OpenAI, GPT-4, artificial intelligence"
					/>
					<p class="mt-1 text-xs text-muted-foreground">
						Case-insensitive text that will be searched in article content
					</p>
				{:else}
					<textarea
						bind:value={filterForm.filter_value}
						placeholder="e.g., Articles about the impact of quantum computing on cybersecurity and encryption"
						class="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
					></textarea>
					<p class="mt-1 text-xs text-muted-foreground">
						Describe the topic you're interested in. Be specific for better AI matching.
					</p>
				{/if}
			</div>

			<!-- Category Selection -->
			<div>
				<label class="mb-1 block text-sm font-medium">Category (Optional)</label>
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
						{filterForm.category_id
							? (categoriesList.find((c) => c.id === filterForm.category_id)?.name ??
								'Select category')
							: 'Global (All Categories)'}
					</Select.Trigger>
					<Select.Content>
						<Select.Item value="null">Global (All Categories)</Select.Item>
						{#each categoriesList as category}
							<Select.Item value={category.id.toString()}>{category.name}</Select.Item>
						{/each}
					</Select.Content>
				</Select.Root>
				<p class="mt-1 text-xs text-muted-foreground">
					Apply this filter globally or to a specific category only
				</p>
			</div>

			<!-- Auto-Star Switch -->
			<div class="flex items-center justify-between rounded-lg border p-4">
				<div class="space-y-0.5">
					<label class="cursor-pointer text-sm font-medium">
						Automatically star matching articles
					</label>
					<p class="text-xs text-muted-foreground">
						Articles that match this filter will be automatically starred
					</p>
				</div>
				<Switch.Switch
					checked={filterForm.auto_star}
					onCheckedChange={(checked) => (filterForm.auto_star = checked)}
				/>
			</div>

			<!-- Auto-Notify Switch -->
			<div class="flex items-center justify-between rounded-lg border p-4">
				<div class="space-y-0.5">
					<label class="cursor-pointer text-sm font-medium"> Send priority alert </label>
					<p class="text-xs text-muted-foreground">
						Create a high-priority in-app alert and forward it to your connected channels when a
						match is found
					</p>
				</div>
				<Switch.Switch
					checked={filterForm.auto_notify}
					onCheckedChange={(checked) => (filterForm.auto_notify = checked)}
				/>
			</div>

			<!-- Enabled Switch -->
			<div class="flex items-center justify-between rounded-lg border p-4">
				<div class="space-y-0.5">
					<label class="cursor-pointer text-sm font-medium"> Enable this filter </label>
					<p class="text-xs text-muted-foreground">
						Activate or deactivate this filter without deleting it
					</p>
				</div>
				<Switch.Switch
					checked={filterForm.enabled}
					onCheckedChange={(checked) => (filterForm.enabled = checked)}
				/>
			</div>
		</div>
		<div class="mt-6 flex justify-end gap-2">
			<Button variant="outline" onclick={() => (showFilterDialog = false)}>Cancel</Button>
			<Button onclick={saveFilter}>{editingFilter ? 'Update Filter' : 'Create Filter'}</Button>
		</div>
	</Dialog.Content>
</Dialog.Root>
