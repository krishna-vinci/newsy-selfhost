<script lang="ts">
import type { PageData } from './$types.js';
import { invalidateAll } from '$app/navigation';
import { Calendar, FileText, Download, Trash2, Plus, Clock } from '@lucide/svelte';
import { toast } from 'svelte-sonner';
import Button from '$lib/components/ui/button/index.svelte';
import Badge from '$lib/components/ui/badge/index.svelte';
import Card from '$lib/components/ui/card/index.svelte';
import * as Table from '$lib/components/ui/table/index.ts';
import * as Dialog from '$lib/components/ui/dialog/index.ts';
import Input from '$lib/components/ui/input/index.svelte';
import * as Select from '$lib/components/ui/select/index.js';
import * as Label from '$lib/components/ui/label/index.ts';
import * as Switch from '$lib/components/ui/switch/index.ts';
import Separator from '$lib/components/ui/separator/index.svelte';
import * as Sidebar from '$lib/components/ui/sidebar/index.js';
import FeedSidebar from '$lib/components/FeedSidebar.svelte';

let { data }: { data: PageData } = $props();

type Schedule = {
	id: number;
	category: string;
	schedule_type: 'daily' | 'weekly';
	schedule_hour: number;
	schedule_minute: number;
	enabled: boolean;
	created_at: string;
	updated_at: string;
};

type ReportFile = {
	filename: string;
	file_size: number;
	generated_at: string;
	category: string;
	report_type: string;
	path: string;
};

type Category = {
	id: number;
	name: string;
	priority: number;
	is_default: boolean;
	web_push_enabled: boolean;
	telegram_enabled: boolean;
};

// State
let schedules = $state<Schedule[]>(data.schedules || []);
let files = $state<ReportFile[]>(data.files || []);
let categories = $state<Category[]>(data.categories || []);
let createDialogOpen = $state(false);
let selectedCategory = $state<string>('');
let selectedScheduleType = $state<string>('daily');
let selectedScheduleHour = $state<number>(0);
let selectedScheduleMinute = $state<number>(0);
let isCreating = $state(false);

// Derived values for select triggers
const categoryTriggerContent = $derived(
	categories.find((c) => c.name === selectedCategory)?.name ?? "Select a category"
);

const scheduleTypeTriggerContent = $derived(
	selectedScheduleType === 'daily' ? `Daily (Every day at ${String(selectedScheduleHour).padStart(2, '0')}:${String(selectedScheduleMinute).padStart(2, '0')})` : 
	selectedScheduleType === 'weekly' ? `Weekly (Every Monday at ${String(selectedScheduleHour).padStart(2, '0')}:${String(selectedScheduleMinute).padStart(2, '0')})` : 
	'Select schedule type'
);

// Functions
async function toggleSchedule(schedule: Schedule) {
	const previousEnabled = schedule.enabled;
	schedule.enabled = !schedule.enabled;
	
	try {
		const response = await fetch(`/api/reports/schedules/${schedule.id}`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				category: schedule.category,
				schedule_type: schedule.schedule_type,
				schedule_hour: schedule.schedule_hour,
				schedule_minute: schedule.schedule_minute,
				enabled: schedule.enabled
			})
		});
		
		if (!response.ok) {
			throw new Error('Failed to update schedule');
		}
		
		toast.success(schedule.enabled ? 'Schedule enabled' : 'Schedule disabled');
	} catch (error) {
		schedule.enabled = previousEnabled;
		console.error('Error toggling schedule:', error);
		toast.error('Failed to update schedule');
	}
}

async function deleteSchedule(scheduleId: number) {
	if (!confirm('Are you sure you want to delete this schedule?')) {
		return;
	}
	
	try {
		const response = await fetch(`/api/reports/schedules/${scheduleId}`, {
			method: 'DELETE'
		});
		
		if (!response.ok) {
			throw new Error('Failed to delete schedule');
		}
		
		schedules = schedules.filter(s => s.id !== scheduleId);
		toast.success('Schedule deleted successfully');
	} catch (error) {
		console.error('Error deleting schedule:', error);
		toast.error('Failed to delete schedule');
	}
}


async function createSchedule() {
	if (!selectedCategory) {
		toast.error('Please select a category');
		return;
	}
	
	if (!selectedScheduleType) {
		toast.error('Please select a schedule type');
		return;
	}
	
	isCreating = true;
	
	try {
		const payload = {
			category: selectedCategory,
			schedule_type: selectedScheduleType,
			schedule_hour: selectedScheduleHour,
			schedule_minute: selectedScheduleMinute,
			enabled: true
		};
		
		console.log('Creating schedule with payload:', payload);
		
		const response = await fetch('/api/reports/schedules', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload)
		});
		
		if (!response.ok) {
			const error = await response.json();
			console.error('Backend error:', error);
			throw new Error(error.detail || JSON.stringify(error));
		}
		
		await invalidateAll();
		createDialogOpen = false;
		selectedCategory = '';
		selectedScheduleType = 'daily';
		selectedScheduleHour = 0;
		selectedScheduleMinute = 0;
		toast.success('Schedule created successfully');
	} catch (error) {
		console.error('Error creating schedule:', error);
		const errorMessage = error instanceof Error ? error.message : 'Failed to create schedule';
		toast.error(errorMessage);
	} finally {
		isCreating = false;
	}
}

async function downloadReport(filename: string) {
	try {
		const response = await fetch(`/api/reports/download/${encodeURIComponent(filename)}`);
		
		if (!response.ok) {
			throw new Error('Failed to download report');
		}
		
		const blob = await response.blob();
		const url = window.URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = filename;
		document.body.appendChild(a);
		a.click();
		window.URL.revokeObjectURL(url);
		document.body.removeChild(a);
		
		toast.success('Report downloaded successfully');
	} catch (error) {
		console.error('Error downloading report:', error);
		toast.error('Failed to download report');
	}
}

function formatFileSize(bytes: number): string {
	if (bytes < 1024) return bytes + ' B';
	if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
	return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function parseReportFilename(filename: string): { category: string; type: string; timestamp: string } {
	// Format: report_{category}_{type}_{timestamp}.md
	const match = filename.match(/report_(.+?)_(starred|daily|weekly)_(.+)\.md/);
	if (match) {
		return {
			category: match[1].replace(/_/g, ' '),
			type: match[2],
			timestamp: match[3].replace(/_/g, ' ').replace(/-/g, '/')
		};
	}
	return { category: 'Unknown', type: 'Unknown', timestamp: 'Unknown' };
}

// Reactive data updates
$effect(() => {
	schedules = data.schedules || [];
	files = data.files || [];
	categories = data.categories || [];
});
</script>

<Sidebar.Provider class="h-full">
<div class="flex w-full h-full">
	<!-- Sidebar -->
	<FeedSidebar 
		selectedCategory="all" 
		onCategorySelect={() => {}} 
		onFeedSelect={() => {}}
		onconfigchanged={async () => await invalidateAll()} 
	/>

	<!-- Main Content -->
	<Sidebar.Inset class="h-full">
		<div class="w-full h-full overflow-auto">
			<div class="px-4 py-4 sm:px-6 sm:py-6 md:px-8 md:py-8">
				<!-- Header -->
				<div class="mb-6 md:mb-8 flex flex-wrap items-center justify-between gap-3">
					<div class="flex items-center gap-2">
						<Sidebar.Trigger />
						<h1 class="text-xl sm:text-2xl font-bold">Reports Dashboard</h1>
					</div>
				</div>

				<div class="grid gap-6 md:gap-8">
				<!-- Schedule Manager Section -->
				<Card class="p-4 sm:p-6">
					<div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-6">
						<div>
							<h2 class="text-xl font-semibold">Report Schedules</h2>
							<p class="text-sm text-muted-foreground">Manage automated daily and weekly reports</p>
						</div>
						<Button onclick={() => createDialogOpen = true} class="w-full sm:w-auto">
							<Plus class="size-4 mr-2" />
							New Schedule
						</Button>
					</div>
					<Separator class="mb-6" />

					{#if schedules.length === 0}
						<div class="flex flex-col items-center justify-center py-12 text-center">
							<Clock class="size-16 mb-4 text-muted-foreground" />
							<p class="text-lg text-muted-foreground">No schedules configured</p>
							<p class="text-sm text-muted-foreground">Create a schedule to automatically generate reports</p>
							<Button variant="outline" class="mt-4" onclick={() => createDialogOpen = true}>
								<Plus class="size-4 mr-2" />
								Create Your First Schedule
							</Button>
						</div>
					{:else}
						<div class="overflow-x-auto -mx-4 sm:mx-0">
						<Table.Root>
							<Table.Header>
								<Table.Row>
									<Table.Head>Category</Table.Head>
									<Table.Head>Schedule Type</Table.Head>
									<Table.Head>Time</Table.Head>
									<Table.Head>Status</Table.Head>
									<Table.Head>Created</Table.Head>
									<Table.Head class="text-right">Actions</Table.Head>
								</Table.Row>
							</Table.Header>
							<Table.Body>
								{#each schedules as schedule (schedule.id)}
									<Table.Row>
										<Table.Cell class="font-medium">{schedule.category}</Table.Cell>
										<Table.Cell>
											<Badge variant={schedule.schedule_type === 'daily' ? 'default' : 'secondary'}>
												<Calendar class="size-3 mr-1" />
												{schedule.schedule_type === 'daily' ? 'Daily' : 'Weekly'}
											</Badge>
										</Table.Cell>
										<Table.Cell class="font-mono text-sm">
											{String(schedule.schedule_hour).padStart(2, '0')}:{String(schedule.schedule_minute).padStart(2, '0')}
										</Table.Cell>
										<Table.Cell>
											<div class="flex items-center gap-2">
												<Switch.Switch
													checked={schedule.enabled}
													onCheckedChange={() => toggleSchedule(schedule)}
												/>
												<span class="text-sm">{schedule.enabled ? 'Enabled' : 'Disabled'}</span>
											</div>
										</Table.Cell>
										<Table.Cell class="text-sm text-muted-foreground">
											{new Date(schedule.created_at).toLocaleDateString()}
										</Table.Cell>
										<Table.Cell class="text-right">
											<Button
												variant="ghost"
												size="icon"
												onclick={() => deleteSchedule(schedule.id)}
											>
												<Trash2 class="size-4" />
											</Button>
										</Table.Cell>
									</Table.Row>
								{/each}
							</Table.Body>
						</Table.Root>
						</div>
					{/if}
				</Card>

				<!-- Generated Reports Section -->
				<Card class="p-4 sm:p-6">
					<div class="mb-6">
						<h2 class="text-xl font-semibold">Generated Reports</h2>
						<p class="text-sm text-muted-foreground">Download your markdown reports</p>
					</div>
					<Separator class="mb-6" />

					{#if files.length === 0}
						<div class="flex flex-col items-center justify-center py-12 text-center">
							<FileText class="size-16 mb-4 text-muted-foreground" />
							<p class="text-lg text-muted-foreground">No reports generated yet</p>
							<p class="text-sm text-muted-foreground">Generate reports from the Feeds page or wait for scheduled reports</p>
						</div>
					{:else}
						<div class="overflow-x-auto -mx-4 sm:mx-0">
						<Table.Root>
							<Table.Header>
								<Table.Row>
									<Table.Head>Category</Table.Head>
									<Table.Head>Type</Table.Head>
									<Table.Head>Generated</Table.Head>
									<Table.Head>Size</Table.Head>
									<Table.Head class="text-right">Actions</Table.Head>
								</Table.Row>
							</Table.Header>
							<Table.Body>
								{#each files as file (file.filename)}
									{@const parsed = parseReportFilename(file.filename)}
									<Table.Row>
										<Table.Cell class="font-medium">{parsed.category}</Table.Cell>
										<Table.Cell>
											<Badge variant="outline">{parsed.type}</Badge>
										</Table.Cell>
										<Table.Cell class="text-sm text-muted-foreground">
											{parsed.timestamp}
										</Table.Cell>
									<Table.Cell class="text-sm text-muted-foreground">
										{formatFileSize(file.file_size)}
									</Table.Cell>
										<Table.Cell class="text-right">
											<Button
												variant="ghost"
												size="sm"
												onclick={() => downloadReport(file.filename)}
											>
												<Download class="size-4 mr-2" />
												Download
											</Button>
										</Table.Cell>
									</Table.Row>
								{/each}
							</Table.Body>
						</Table.Root>
						</div>
					{/if}
				</Card>
			</div>
			</div>
		</div>
	</Sidebar.Inset>
</div>
</Sidebar.Provider>

<!-- Create Schedule Dialog -->
<Dialog.Root bind:open={createDialogOpen}>
<Dialog.Content class="max-w-[95vw] sm:max-w-md max-h-[90vh] overflow-y-auto">
	<Dialog.Header>
		<Dialog.Title>Create Report Schedule</Dialog.Title>
		<Dialog.Description>Set up an automated schedule to generate reports for a category</Dialog.Description>
	</Dialog.Header>
	<div class="grid gap-4">
		<div class="grid gap-2">
			<Label.Label for="category">Category</Label.Label>
			<Select.Root type="single" bind:value={selectedCategory}>
				<Select.Trigger id="category" class="w-full">
					{categoryTriggerContent}
				</Select.Trigger>
				<Select.Content>
					{#each categories as category (category.id)}
						<Select.Item value={category.name} label={category.name}>
							{category.name}
						</Select.Item>
					{/each}
				</Select.Content>
			</Select.Root>
		</div>

		<div class="grid gap-2">
			<Label.Label for="schedule-type">Schedule Type</Label.Label>
			<Select.Root type="single" bind:value={selectedScheduleType}>
				<Select.Trigger id="schedule-type" class="w-full">
					{scheduleTypeTriggerContent}
				</Select.Trigger>
				<Select.Content>
					<Select.Item value="daily" label="Daily">
						Daily (Every day)
					</Select.Item>
					<Select.Item value="weekly" label="Weekly">
						Weekly (Every Monday)
					</Select.Item>
				</Select.Content>
			</Select.Root>
		</div>

		<div class="grid grid-cols-2 gap-4">
			<div class="grid gap-2">
				<Label.Label for="schedule-hour">Hour (0-23)</Label.Label>
				<input
					id="schedule-hour"
					type="number"
					min="0"
					max="23"
					bind:value={selectedScheduleHour}
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
				/>
			</div>
			<div class="grid gap-2">
				<Label.Label for="schedule-minute">Minute (0-59)</Label.Label>
				<input
					id="schedule-minute"
					type="number"
					min="0"
					max="59"
					bind:value={selectedScheduleMinute}
					class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
				/>
			</div>
		</div>
	</div>

	<Dialog.Footer>
		<Button variant="outline" onclick={() => createDialogOpen = false}>
			Cancel
		</Button>
		<Button onclick={createSchedule} disabled={isCreating}>
			{isCreating ? 'Creating...' : 'Create Schedule'}
		</Button>
	</Dialog.Footer>
</Dialog.Content>
</Dialog.Root>
