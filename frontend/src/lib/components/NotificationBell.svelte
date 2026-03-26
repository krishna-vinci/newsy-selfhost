<script lang="ts">
	import { onMount } from 'svelte';
	import Button from '$lib/components/ui/button/index.svelte';
	import * as Sheet from '$lib/components/ui/sheet/index.js';
	import Badge from '$lib/components/ui/badge/index.svelte';
	import { Bell, CheckCheck, ExternalLink, Loader2 } from '@lucide/svelte';

	type NotificationItem = {
		id: number;
		channel: string;
		kind: string;
		title: string;
		body: string | null;
		link: string | null;
		is_read: boolean;
		sent_at: string;
	};

	let open = $state(false);
	let items = $state<NotificationItem[]>([]);
	let unreadCount = $state(0);
	let isLoading = $state(false);
	let isMarkingAllRead = $state(false);

	function formatTimeAgo(dateString: string): string {
		const timestamp = new Date(dateString).getTime();
		const seconds = Math.max(1, Math.floor((Date.now() - timestamp) / 1000));
		if (seconds < 60) return 'just now';
		if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
		if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
		if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
		return new Date(dateString).toLocaleDateString();
	}

	async function loadSummary() {
		try {
			const response = await fetch('/api/notifications/summary');
			if (!response.ok) throw new Error('Failed to load notification summary');
			const payload = await response.json();
			unreadCount = payload.unread_count || 0;
		} catch (error) {
			console.error('Error loading notification summary:', error);
		}
	}

	async function loadNotifications() {
		isLoading = true;
		try {
			const response = await fetch('/api/notifications?limit=40');
			if (!response.ok) throw new Error('Failed to load notifications');
			const payload = await response.json();
			items = payload.items || [];
			unreadCount = payload.unread_count || 0;
		} catch (error) {
			console.error('Error loading notifications:', error);
		} finally {
			isLoading = false;
		}
	}

	async function updateReadState(notificationId: number, isRead: boolean) {
		await fetch(`/api/notifications/${notificationId}`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ is_read: isRead })
		});
	}

	async function markAllRead() {
		isMarkingAllRead = true;
		try {
			const response = await fetch('/api/notifications/read-all', { method: 'POST' });
			if (!response.ok) throw new Error('Failed to mark notifications as read');
			items = items.map((item) => ({ ...item, is_read: true }));
			unreadCount = 0;
		} catch (error) {
			console.error('Error marking notifications as read:', error);
		} finally {
			isMarkingAllRead = false;
		}
	}

	async function openNotification(item: NotificationItem) {
		if (!item.is_read) {
			try {
				await updateReadState(item.id, true);
				if (item.link && item.kind !== 'article_batch') {
					await fetch('/api/articles/mark-as-read', {
						method: 'POST',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({ links: [item.link] })
					});
				}
				items = items.map((entry) => (entry.id === item.id ? { ...entry, is_read: true } : entry));
				unreadCount = Math.max(0, unreadCount - 1);
			} catch (error) {
				console.error('Error marking notification as read:', error);
			}
		}

		if (item.link) {
			window.open(item.link, '_blank', 'noopener,noreferrer');
		}
	}

	$effect(() => {
		if (open) {
			loadNotifications();
		}
	});

	onMount(() => {
		loadSummary();

		const interval = window.setInterval(loadSummary, 60000);
		const onFocus = () => loadSummary();
		window.addEventListener('focus', onFocus);

		return () => {
			window.clearInterval(interval);
			window.removeEventListener('focus', onFocus);
		};
	});
</script>

<Button variant="outline" size="icon" class="relative" onclick={() => (open = true)}>
	<Bell class="h-4 w-4" />
	<span class="sr-only">Open notifications</span>
	{#if unreadCount > 0}
		<Badge
			class="absolute -top-1.5 -right-1.5 h-5 min-w-5 justify-center rounded-full px-1 text-[10px]"
		>
			{unreadCount > 99 ? '99+' : unreadCount}
		</Badge>
	{/if}
</Button>

<Sheet.Root bind:open>
	<Sheet.Content side="right" class="w-full max-w-md p-0">
		<Sheet.Header class="border-b p-4 text-left">
			<div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
				<div>
					<Sheet.Title>Notifications</Sheet.Title>
					<Sheet.Description
						>Article alerts, filter matches, and delivery updates for your account.</Sheet.Description
					>
				</div>
				<Button
					variant="ghost"
					size="sm"
					onclick={markAllRead}
					disabled={isMarkingAllRead || unreadCount === 0}
				>
					{#if isMarkingAllRead}
						<Loader2 class="mr-2 h-4 w-4 animate-spin" />
					{/if}
					<CheckCheck class="mr-2 h-4 w-4" />
					Mark all read
				</Button>
			</div>
		</Sheet.Header>

		<div class="max-h-[calc(100dvh-96px)] overflow-y-auto p-4">
			{#if isLoading}
				<div class="flex items-center justify-center py-12 text-sm text-muted-foreground">
					<Loader2 class="mr-2 h-4 w-4 animate-spin" />
					Loading notifications…
				</div>
			{:else if !items.length}
				<div class="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
					No notifications yet.
				</div>
			{:else}
				<div class="space-y-3">
					{#each items as item (item.id)}
						<button
							type="button"
							class={`w-full rounded-lg border p-4 text-left transition-colors hover:bg-accent/40 ${item.is_read ? 'bg-background' : 'bg-accent/20'}`}
							onclick={() => openNotification(item)}
						>
							<div class="mb-2 flex items-start justify-between gap-3">
								<div class="min-w-0">
									<p class="truncate text-sm font-medium">{item.title}</p>
									<p class="mt-1 text-xs text-muted-foreground">{formatTimeAgo(item.sent_at)}</p>
								</div>
								<div class="flex items-center gap-2">
									{#if !item.is_read}
										<span class="h-2.5 w-2.5 rounded-full bg-primary"></span>
									{/if}
									{#if item.link}
										<ExternalLink class="h-4 w-4 text-muted-foreground" />
									{/if}
								</div>
							</div>
							{#if item.body}
								<p class="line-clamp-4 text-sm text-muted-foreground">{item.body}</p>
							{/if}
						</button>
					{/each}
				</div>
			{/if}
		</div>
	</Sheet.Content>
</Sheet.Root>
