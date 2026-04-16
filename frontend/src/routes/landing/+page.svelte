<script lang="ts">
	import {
		ArrowUpRight,
		Bell,
		BrainCircuit,
		ChevronRight,
		Code2,
		FileText,
		Github,
		Globe,
		LayoutGrid,
		Rss,
		Sparkles,
		Terminal,
		Zap
	} from '@lucide/svelte';
	import Badge from '$lib/components/ui/badge/index.svelte';
	import Button from '$lib/components/ui/button/index.svelte';
	import Card from '$lib/components/ui/card/index.svelte';
	import { Separator } from '$lib/components/ui/separator/index.js';

	const featureCards = [
		{
			icon: Rss,
			title: 'Multi-source ingestion',
			description:
				'Subscribe to RSS, YouTube channels, and Reddit feeds from a unified search. Organize into categories that match how you think.',
			detail: 'Automatic favicon extraction, OPML import, and feed health monitoring built in.',
			accent: 'from-orange-500/20 to-amber-500/10',
			iconBg: 'bg-orange-500/10 text-orange-600 dark:text-orange-400'
		},
		{
			icon: LayoutGrid,
			title: 'Adaptive reading layouts',
			description:
				'Switch between card, headline, and column views. Full-content extraction strips away ads and navigation for distraction-free reading.',
			detail: 'Keyboard shortcuts, star/save workflow, and per-category layout memory.',
			accent: 'from-blue-500/20 to-cyan-500/10',
			iconBg: 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
		},
		{
			icon: BrainCircuit,
			title: 'AI-powered filtering',
			description:
				'Connect any OpenAI-compatible model. Per-category relevance scoring, automatic summaries, and signal-from-noise filtering.',
			detail: 'Works with local models (Ollama), OpenAI, Anthropic, or any compatible API.',
			accent: 'from-violet-500/20 to-purple-500/10',
			iconBg: 'bg-violet-500/10 text-violet-600 dark:text-violet-400'
		},
		{
			icon: FileText,
			title: 'Automated reports',
			description:
				'Schedule daily or weekly markdown digests. Starred items, category rollups, and AI summaries combined into one document.',
			detail: 'Reports are Markdown-native — pipe them to email, Slack, or your own tooling.',
			accent: 'from-emerald-500/20 to-teal-500/10',
			iconBg: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
		},
		{
			icon: Bell,
			title: 'Push & Telegram alerts',
			description:
				'Category-level browser push and Telegram notifications. Know about critical updates the moment they appear.',
			detail: 'Fine-grained per-category controls. No global firehose — only what you care about.',
			accent: 'from-rose-500/20 to-pink-500/10',
			iconBg: 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
		},
		{
			icon: Code2,
			title: 'External REST API',
			description:
				'Read-oriented REST endpoints with SSE streaming. Integrate curated feeds into trading bots, dashboards, or research systems.',
			detail: 'Bearer token auth, pagination, category/feed filtering, and real-time streaming.',
			accent: 'from-sky-500/20 to-indigo-500/10',
			iconBg: 'bg-sky-500/10 text-sky-600 dark:text-sky-400'
		}
	];

	const journeySteps = [
		{
			num: '01',
			title: 'Discover & curate',
			desc: 'Search across RSS, YouTube, and Reddit from one search bar. Subscribe, categorize, and organize sources into logical groups.',
			icon: Globe,
			mockTitle: 'Feed Discovery',
			mockItems: [
				{ name: 'Hacker News', type: 'RSS', status: 'Subscribed' },
				{ name: 'r/machinelearning', type: 'Reddit', status: 'New' },
				{ name: '3Blue1Brown', type: 'YouTube', status: 'Subscribed' }
			]
		},
		{
			num: '02',
			title: 'Read with clarity',
			desc: 'Full-content extraction, multiple layouts, AI relevance scoring, and starred items. Focus on signal, skip noise.',
			icon: Sparkles,
			mockTitle: 'AI Scored Feed',
			mockItems: [
				{ name: 'GPT-5 architecture paper', score: '94', tag: 'High' },
				{ name: 'New React compiler RFC', score: '87', tag: 'High' },
				{ name: 'Weekend sale roundup', score: '12', tag: 'Low' }
			]
		},
		{
			num: '03',
			title: 'Route everywhere',
			desc: 'Automated reports, push/Telegram alerts, and a full REST API with SSE streaming for downstream integrations.',
			icon: Zap,
			mockTitle: 'Delivery Pipeline',
			mockItems: [
				{ name: 'Daily AI digest', dest: 'Email + Telegram', freq: 'Daily' },
				{ name: 'Security alerts', dest: 'Push notification', freq: 'Real-time' },
				{ name: 'Weekly rollup', dest: 'Markdown report', freq: 'Weekly' }
			]
		}
	];

	const archLayers = [
		{
			label: 'Frontend',
			tech: 'SvelteKit · TypeScript · Tailwind · shadcn-svelte',
			color: 'bg-orange-500/15 text-orange-600 dark:text-orange-400 border-orange-500/20'
		},
		{
			label: 'API Gateway',
			tech: 'FastAPI · Python · JWT auth · REST + SSE',
			color: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
		},
		{
			label: 'Workers',
			tech: 'Go services · Feed polling · AI pipeline · Content extraction',
			color: 'bg-violet-500/15 text-violet-600 dark:text-violet-400 border-violet-500/20'
		},
		{
			label: 'Data layer',
			tech: 'PostgreSQL · Redis · Full-text search · Migrations',
			color: 'bg-sky-500/15 text-sky-600 dark:text-sky-400 border-sky-500/20'
		}
	];

	const stats = [
		{ value: '6', label: 'Services' },
		{ value: 'SSE', label: 'Real-time' },
		{ value: '∞', label: 'Self-hosted' },
		{ value: 'MIT', label: 'License' }
	];
</script>

<div class="relative">
	<!-- Background gradients -->
	<div
		class="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(99,102,241,0.12),transparent),radial-gradient(ellipse_60%_40%_at_80%_100%,rgba(168,85,247,0.06),transparent)]"
	></div>

	<div class="relative">
		<!-- ─── HERO ─── -->
		<section id="home" class="mx-auto max-w-6xl px-4 pt-12 pb-16 sm:px-6 lg:px-8 lg:pt-20 lg:pb-24">
			<div class="grid gap-12 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
				<div class="space-y-6">
					<div class="flex flex-wrap items-center gap-2">
						<Badge
							variant="outline"
							class="rounded-full border-primary/30 bg-primary/5 px-3 py-1 text-xs font-medium"
						>
							Open source · Self-hosted
						</Badge>
						<Badge
							variant="outline"
							class="rounded-full border-violet-500/30 bg-violet-500/5 px-3 py-1 text-xs font-medium text-violet-600 dark:text-violet-400"
						>
							Full-stack · Docker Compose
						</Badge>
					</div>

					<h1
						class="text-4xl font-bold tracking-tight sm:text-5xl lg:text-[3.5rem] lg:leading-[1.1]"
					>
						Your news.
						<br />
						<span
							class="bg-gradient-to-r from-primary via-violet-500 to-primary bg-[length:200%_auto] bg-clip-text text-transparent"
							style="animation: shimmer 6s ease-in-out infinite"
							>Your server.</span
						>
						<br />
						Zero noise.
					</h1>

					<p class="max-w-lg text-base leading-relaxed text-muted-foreground sm:text-lg">
						Newsy is a self-hosted news aggregation platform with AI filtering, multi-format
						ingestion, scheduled reports, and a full external API — built for developers who want
						control over their information flow.
					</p>

					<div class="flex flex-wrap items-center gap-3 pt-1">
						<Button
							href="https://github.com/krishna-vinci/newsy-selfhost"
							target="_blank"
							rel="noreferrer"
							class="gap-2"
						>
							<Github class="size-4" />
							View on GitHub
							<ArrowUpRight class="size-3.5" />
						</Button>
					<Button href="/landing/api-doc" variant="outline" class="gap-2">
						<Terminal class="size-4" />
						API docs
					</Button>
						<Button href="/landing/help" variant="ghost" class="gap-2 text-muted-foreground">
							Help
							<ChevronRight class="size-3.5" />
						</Button>
					</div>

					<div class="flex gap-6 border-t border-border/60 pt-5">
						{#each stats as stat (stat.label)}
							<div class="text-center">
								<div class="text-xl font-bold tracking-tight">{stat.value}</div>
								<div class="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
									{stat.label}
								</div>
							</div>
						{/each}
					</div>
				</div>

				<!-- Mock UI preview panel -->
				<div class="relative">
					<div
						class="absolute -inset-4 rounded-3xl bg-gradient-to-br from-primary/10 via-violet-500/5 to-transparent blur-2xl"
					></div>
					<Card
						class="relative overflow-hidden rounded-2xl border-border/60 bg-card/80 p-0 shadow-xl backdrop-blur"
					>
						<div
							class="flex items-center gap-2 border-b border-border/50 bg-muted/30 px-4 py-2.5"
						>
							<div class="flex gap-1.5">
								<div class="size-2.5 rounded-full bg-red-400/60"></div>
								<div class="size-2.5 rounded-full bg-yellow-400/60"></div>
								<div class="size-2.5 rounded-full bg-green-400/60"></div>
							</div>
							<div
								class="ml-2 flex-1 rounded-md bg-background/50 px-3 py-1 text-[11px] text-muted-foreground"
							>
								newsy / feeds
							</div>
						</div>
						<div class="space-y-0 divide-y divide-border/40 p-0">
							{#each [{ cat: 'Tech', count: 12, color: 'bg-blue-500', score: '↑ 94' }, { cat: 'Finance', count: 8, color: 'bg-emerald-500', score: '↑ 87' }, { cat: 'AI Research', count: 15, color: 'bg-violet-500', score: '↑ 96' }, { cat: 'Security', count: 6, color: 'bg-amber-500', score: '↑ 72' }] as feed (feed.cat)}
								<div
									class="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/20"
								>
									<div class="size-2 rounded-full {feed.color}"></div>
									<div class="flex-1">
										<div class="text-sm font-medium">{feed.cat}</div>
										<div class="text-xs text-muted-foreground">
											{feed.count} unread · AI score {feed.score}
										</div>
									</div>
									<Badge variant="secondary" class="rounded-full px-2 py-0.5 text-[10px]"
										>{feed.count}</Badge
									>
								</div>
							{/each}
							<div class="flex items-center justify-between bg-muted/10 px-4 py-2.5">
								<div class="flex items-center gap-2 text-xs text-muted-foreground">
									<Sparkles class="size-3" />
									AI filter active
								</div>
								<div class="text-[10px] text-muted-foreground">41 items · 4 sources</div>
							</div>
						</div>
					</Card>
				</div>
			</div>
		</section>

		<!-- ─── FEATURES ─── -->
		<section id="features" class="border-t border-border/40 bg-muted/20 py-16 lg:py-24">
			<div class="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
				<div class="space-y-16">
					<!-- Feature cards -->
					<div>
						<div class="mb-10 max-w-2xl space-y-3">
							<div
								class="text-xs font-semibold tracking-[0.25em] text-muted-foreground uppercase"
							>
								Capabilities
							</div>
							<h2 class="text-3xl font-bold tracking-tight sm:text-4xl">
								Everything you need to own your information pipeline.
							</h2>
							<p class="text-base leading-relaxed text-muted-foreground">
								From source discovery to downstream delivery — a complete system for curating, filtering, and distributing news on your terms.
							</p>
						</div>

						<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
							{#each featureCards as feature (feature.title)}
								<Card
									class="group relative overflow-hidden rounded-2xl border-border/50 bg-card/80 p-5 shadow-sm transition-all duration-300 hover:shadow-md hover:-translate-y-0.5"
								>
									<div
										class="absolute inset-0 bg-gradient-to-br {feature.accent} opacity-0 transition-opacity duration-300 group-hover:opacity-100"
									></div>
									<div class="relative space-y-4">
										<div
											class="flex h-10 w-10 items-center justify-center rounded-xl {feature.iconBg}"
										>
											<feature.icon class="size-5" />
										</div>
										<div class="space-y-2">
											<h3 class="text-base font-semibold">{feature.title}</h3>
											<p class="text-sm leading-relaxed text-muted-foreground">
												{feature.description}
											</p>
											<p class="text-xs leading-relaxed text-muted-foreground/70 italic">
												{feature.detail}
											</p>
										</div>
									</div>
								</Card>
							{/each}
						</div>
					</div>

					<!-- Journey / How it works -->
					<div>
						<div class="mb-10 max-w-2xl space-y-3">
							<div
								class="text-xs font-semibold tracking-[0.25em] text-muted-foreground uppercase"
							>
								The journey
							</div>
							<h2 class="text-2xl font-bold tracking-tight sm:text-3xl">
								From discovery to delivery in three steps.
							</h2>
						</div>

						<div class="space-y-6">
							{#each journeySteps as step (step.num)}
								<div
									class="grid gap-6 overflow-hidden rounded-2xl border border-border/50 bg-card/60 shadow-sm backdrop-blur lg:grid-cols-[1fr_1fr]"
								>
									<!-- Text side -->
									<div class="flex flex-col justify-center px-6 py-8 sm:px-10">
										<div
											class="mb-4 text-5xl font-black tracking-tighter text-primary/10"
										>
											{step.num}
										</div>
										<div
											class="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary"
										>
											<step.icon class="size-4.5" />
										</div>
										<h3 class="mb-2 text-lg font-semibold">{step.title}</h3>
										<p class="text-sm leading-relaxed text-muted-foreground">{step.desc}</p>
									</div>
									<!-- Mock panel side -->
									<div class="border-t border-border/40 bg-muted/10 lg:border-t-0 lg:border-l">
										<div
											class="flex items-center gap-2 border-b border-border/30 px-4 py-2"
										>
											<div class="size-2 rounded-full bg-primary/40"></div>
											<span class="text-[11px] font-medium text-muted-foreground"
												>{step.mockTitle}</span
											>
										</div>
										<div class="divide-y divide-border/30">
											{#each step.mockItems as item, i}
												<div
													class="flex items-center justify-between px-4 py-3 text-sm transition-colors hover:bg-muted/20"
												>
													<span class="font-medium text-foreground/90">{item.name}</span>
													<div class="flex items-center gap-2">
														{#if 'type' in item}
															<Badge variant="outline" class="rounded px-1.5 py-0 text-[10px]">{item.type}</Badge>
															<span class="text-[10px] text-muted-foreground">{item.status}</span>
														{:else if 'score' in item}
															<span class="font-mono text-xs text-muted-foreground">{item.score}</span>
															<Badge variant={item.tag === 'High' ? 'default' : 'secondary'} class="rounded px-1.5 py-0 text-[10px]">{item.tag}</Badge>
														{:else if 'dest' in item}
															<span class="text-[10px] text-muted-foreground">{item.dest}</span>
															<Badge variant="outline" class="rounded px-1.5 py-0 text-[10px]">{item.freq}</Badge>
														{/if}
													</div>
												</div>
											{/each}
										</div>
									</div>
								</div>
							{/each}
						</div>
					</div>

					<!-- Architecture -->
					<div class="grid gap-10 lg:grid-cols-2 lg:items-start">
						<div class="space-y-5">
							<div>
								<div
									class="text-xs font-semibold tracking-[0.25em] text-muted-foreground uppercase"
								>
									Architecture
								</div>
								<h2 class="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
									A clean, composable stack.
								</h2>
								<p class="mt-3 text-sm leading-relaxed text-muted-foreground sm:text-base">
									Four layers working together — a reactive frontend, a Python API gateway, Go
									background workers for feed polling and AI, and a proven data layer. All containerized
									with Docker Compose.
								</p>
							</div>

							<div class="space-y-2.5">
								{#each archLayers as layer (layer.label)}
									<div
										class="flex items-center gap-4 rounded-xl border {layer.color} px-4 py-3 transition-all duration-200 hover:scale-[1.01]"
									>
										<div class="text-sm font-semibold">{layer.label}</div>
										<Separator orientation="vertical" class="h-4 bg-current opacity-20" />
										<div class="text-xs opacity-80">{layer.tech}</div>
									</div>
								{/each}
							</div>
						</div>

						<!-- Data flow diagram mock -->
						<Card class="overflow-hidden rounded-2xl border-border/50 bg-card/80 p-0 shadow-sm">
							<div class="border-b border-border/40 bg-muted/20 px-4 py-2.5">
								<span class="text-[11px] font-medium text-muted-foreground">Data Flow</span>
							</div>
							<div class="space-y-3 p-5">
								{#each [{ from: 'RSS / YouTube / Reddit', to: 'Go Feed Workers', arrow: true }, { from: 'Go Feed Workers', to: 'PostgreSQL + Redis', arrow: true }, { from: 'AI Pipeline', to: 'Score & Summarize', arrow: true }, { from: 'FastAPI Gateway', to: 'REST + SSE → Clients', arrow: false }] as flow, i}
									<div class="flex items-center gap-3">
										<div class="flex-1 rounded-lg bg-muted/30 px-3 py-2 text-xs font-medium">
											{flow.from}
										</div>
										<ChevronRight class="size-4 text-muted-foreground/50 shrink-0" />
										<div class="flex-1 rounded-lg bg-muted/30 px-3 py-2 text-xs font-medium">
											{flow.to}
										</div>
									</div>
								{/each}
							</div>
						</Card>
					</div>
				</div>
			</div>
		</section>

		<!-- ─── OPEN SOURCE CTA ─── -->
		<section
			class="border-t border-border/40 bg-muted/10"
		>
			<div class="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:px-8 lg:py-24">
				<div
					class="relative overflow-hidden rounded-3xl border border-border/50 bg-card/60 p-8 shadow-sm backdrop-blur sm:p-12"
				>
					<div
						class="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-violet-500/5"
					></div>
					<div
						class="relative flex flex-col items-start gap-8 lg:flex-row lg:items-center lg:justify-between"
					>
						<div class="space-y-3">
							<h2 class="text-2xl font-bold tracking-tight sm:text-3xl">
								Built to own, not to rent.
							</h2>
							<p class="max-w-xl text-sm leading-relaxed text-muted-foreground sm:text-base">
								Newsy is fully open-source and designed to run on your own infrastructure. Clone, configure,
								deploy — no vendor lock-in, no subscription, full data ownership.
							</p>
							<div class="flex flex-wrap gap-2 pt-1">
								{#each ['Docker Compose', 'PostgreSQL', 'Redis', 'Go workers', 'FastAPI', 'SvelteKit'] as tag (tag)}
									<Badge
										variant="outline"
										class="rounded-full border-border/60 px-2.5 py-0.5 text-xs">{tag}</Badge
									>
								{/each}
							</div>
						</div>
						<div class="flex flex-wrap gap-3">
							<Button
								href="https://github.com/krishna-vinci/newsy-selfhost"
								target="_blank"
								rel="noreferrer"
								size="lg"
								class="gap-2 whitespace-nowrap"
							>
								<Github class="size-4" />
								View on GitHub
							</Button>
							<Button
								href="/landing/help"
								variant="outline"
								size="lg"
								class="gap-2 whitespace-nowrap"
							>
								Get help
							</Button>
						</div>
					</div>
				</div>
			</div>
		</section>

		<!-- Footer -->
		<footer class="border-t border-border/40 py-8">
			<div class="mx-auto flex max-w-6xl flex-col items-center gap-4 px-4 sm:flex-row sm:justify-between sm:px-6 lg:px-8">
				<div class="text-xs text-muted-foreground/60">
					Built with SvelteKit, FastAPI, Go, PostgreSQL, Redis & Docker
				</div>
				<div class="flex items-center gap-4 text-xs text-muted-foreground/60">
					<a href="/landing/help" class="transition-colors hover:text-muted-foreground">Help</a>
					<a href="https://github.com/krishna-vinci/newsy-selfhost" target="_blank" rel="noreferrer" class="transition-colors hover:text-muted-foreground">GitHub</a>
					<span>MIT License</span>
				</div>
			</div>
		</footer>
	</div>
</div>

<style>
	@keyframes shimmer {
		0%, 100% { background-position: 0% center; }
		50% { background-position: 100% center; }
	}
</style>
