<script lang="ts">
	import {
		ArrowUpRight,
		BookOpen,
		Github,
		Heart,
		HelpCircle,
		MessageCircle,
		Rocket,
		Server,
		Shield
	} from '@lucide/svelte';
	import Badge from '$lib/components/ui/badge/index.svelte';
	import Button from '$lib/components/ui/button/index.svelte';
	import Card from '$lib/components/ui/card/index.svelte';

	const sections = [
		{
			icon: Rocket,
			title: 'Getting started',
			items: [
				'Clone the repository from GitHub',
				'Copy .env.example to .env and configure your settings',
				'Run docker compose up -d to start all services',
				'Open the app and complete the bootstrap flow to create your admin account',
				'Add your first feeds via the search bar'
			]
		},
		{
			icon: Server,
			title: 'Configuration',
			items: [
				'AI filtering: Set OPENAI_BASE_URL and OPENAI_API_KEY in .env (works with OpenAI-compatible APIs)',
				'Telegram alerts: Configure TELEGRAM_BOT_TOKEN and complete setup from the Notifications settings UI',
				'Push notifications: Enabled automatically via the browser — requires HTTPS in production',
				'External API: Generate a personal API token from Settings → API to use REST and SSE endpoints',
				'Reports: Configure schedule and categories from the Reports page'
			]
		},
		{
			icon: Shield,
			title: 'Security & deployment',
			items: [
				'Application routes use session-based auth, while the dedicated external API uses Bearer tokens',
				'Use a reverse proxy (Caddy, Nginx) for HTTPS termination in production',
				'Database credentials and secrets are managed through environment variables',
				'The app supports single-user and multi-user modes'
			]
		},
		{
			icon: HelpCircle,
			title: 'Troubleshooting',
			items: [
				'Feeds not updating? Check the scheduler logs with docker compose logs go-scheduler',
				'AI scoring not working? Verify your OPENAI_BASE_URL is reachable from the app container',
				'Push notifications not arriving? Ensure your browser has notification permissions and the app is served over HTTPS',
				'Content extraction failing? Some sites block automated extraction — this is expected'
			]
		}
	];
</script>

<div class="relative">
	<div
		class="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_60%_40%_at_50%_0%,rgba(99,102,241,0.08),transparent)]"
	></div>

	<div class="relative mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8 lg:py-20">
		<div class="mb-12 space-y-4">
			<div class="flex items-center gap-2">
				<Badge
					variant="outline"
					class="rounded-full border-primary/30 bg-primary/5 px-3 py-1 text-xs font-medium"
				>
					Help & Support
				</Badge>
			</div>
			<h1 class="text-3xl font-bold tracking-tight sm:text-4xl">
				Get up and running with Newsy
			</h1>
			<p class="max-w-2xl text-base leading-relaxed text-muted-foreground">
				Everything you need to deploy, configure, and operate your self-hosted Newsy instance.
			</p>
		</div>

		<div class="space-y-6">
			{#each sections as section (section.title)}
				<Card class="overflow-hidden rounded-2xl border-border/50 bg-card/80 p-0 shadow-sm">
					<div class="flex items-center gap-3 border-b border-border/40 bg-muted/20 px-5 py-3.5">
						<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
							<section.icon class="size-4" />
						</div>
						<h2 class="text-base font-semibold">{section.title}</h2>
					</div>
					<ul class="divide-y divide-border/30">
						{#each section.items as item, i}
							<li class="px-5 py-3 text-sm leading-relaxed text-muted-foreground">
								<span class="mr-2 font-mono text-xs text-primary/50">{i + 1}.</span>
								{item}
							</li>
						{/each}
					</ul>
				</Card>
			{/each}
		</div>

		<!-- Contributing & links -->
		<div class="mt-12 grid gap-4 sm:grid-cols-2">
			<Card class="rounded-2xl border-border/50 bg-card/80 p-6 shadow-sm">
				<div class="flex items-center gap-3 mb-3">
					<Heart class="size-5 text-rose-500" />
					<h3 class="text-base font-semibold">Contributing</h3>
				</div>
				<p class="mb-4 text-sm leading-relaxed text-muted-foreground">
					Newsy is open source under the Apache 2.0 license. Contributions, bug reports, and feature requests are welcome.
				</p>
				<Button
					href="https://github.com/krishna-vinci/newsy-selfhost"
					target="_blank"
					rel="noreferrer"
					variant="outline"
					class="gap-2"
				>
					<Github class="size-4" />
					Contribute on GitHub
					<ArrowUpRight class="size-3.5" />
				</Button>
			</Card>

			<Card class="rounded-2xl border-border/50 bg-card/80 p-6 shadow-sm">
				<div class="flex items-center gap-3 mb-3">
					<MessageCircle class="size-5 text-blue-500" />
					<h3 class="text-base font-semibold">Get in touch</h3>
				</div>
				<p class="mb-4 text-sm leading-relaxed text-muted-foreground">
					Found a bug or have a question? Open an issue on GitHub or check existing discussions for answers.
				</p>
				<Button
					href="https://github.com/krishna-vinci/newsy-selfhost/issues"
					target="_blank"
					rel="noreferrer"
					variant="outline"
					class="gap-2"
				>
					<BookOpen class="size-4" />
					Open an issue
					<ArrowUpRight class="size-3.5" />
				</Button>
			</Card>
		</div>

		<div class="mt-8 text-center">
			<Button href="/landing" variant="ghost" class="text-muted-foreground">
				← Back to landing page
			</Button>
		</div>
	</div>
</div>
