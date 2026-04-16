<script lang="ts">
	import {
		ArrowUpRight,
		Github,
		Key,
		Server,
		Settings,
		Shield,
		Terminal,
		Zap
	} from '@lucide/svelte';
	import Badge from '$lib/components/ui/badge/index.svelte';
	import Button from '$lib/components/ui/button/index.svelte';
	import Card from '$lib/components/ui/card/index.svelte';
	import { Separator } from '$lib/components/ui/separator/index.js';

	let activeTab: Record<string, 'curl' | 'python'> = $state({
		articles: 'curl',
		stream: 'curl',
		extract: 'curl'
	});

	// ── curl examples ──
	const curlArticles = `curl -sS \\
  -H "Authorization: Bearer YOUR_API_TOKEN" \\
  "https://your-instance.com/api/external/articles?category=World%20Tech&limit=5&include_content=true"`;

	const curlStream = `curl -N \\
  -H "Authorization: Bearer YOUR_API_TOKEN" \\
  -H "Last-Event-ID: a12345-n678" \\
  "https://your-instance.com/api/external/stream?category=World%20Tech&include_notifications=true"`;

	const curlExtract = `curl -sS \\
  -X POST \\
  -H "Authorization: Bearer YOUR_API_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"force_refresh":false}' \\
  "https://your-instance.com/api/external/articles/9876/extract"`;

	// ── Python examples ──
	const pyArticles = `import requests

BASE = "https://your-instance.com/api/external"
TOKEN = "YOUR_API_TOKEN"
headers = {"Authorization": f"Bearer {TOKEN}"}

resp = requests.get(
    f"{BASE}/articles",
    headers=headers,
    params={
        "category": "World Tech",
        "limit": 5,
        "include_content": True,
    },
)
data = resp.json()
for item in data["items"]:
    print(item["title"], item["feed"]["name"])`;

	const pyStream = `import requests

BASE = "https://your-instance.com/api/external"
TOKEN = "YOUR_API_TOKEN"
headers = {"Authorization": f"Bearer {TOKEN}"}

with requests.get(
    f"{BASE}/stream",
    headers=headers,
    params={"category": "World Tech", "include_notifications": True},
    stream=True,
) as resp:
    for line in resp.iter_lines(decode_unicode=True):
        if line.startswith("data: "):
            print(line[6:])`;

	const pyExtract = `import requests

BASE = "https://your-instance.com/api/external"
TOKEN = "YOUR_API_TOKEN"
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

resp = requests.post(
    f"{BASE}/articles/9876/extract",
    headers=headers,
    json={"force_refresh": False},
)
result = resp.json()
print(result["item"]["content"][:200])`;

	const tokenSteps = [
		'Open your Newsy instance and go to Settings → API.',
		'Turn on Dedicated external API and enable SSE if you want streaming.',
		'Click Generate token, name it for the consuming app, and copy it immediately.',
		'Use the token in the Authorization header as a Bearer token for every request.'
	];

	const pythonClientSummary = [
		'Located at examples/python_external_api_client.py in the repository.',
		'Fetches a recent article snapshot and requests on-demand extraction when full content is missing.',
		'Tails the SSE stream and stores the last cursor locally for reconnect support.',
		'Useful as a ready-to-adapt template for trading, analytics, or research pipelines.'
	];

	// ── Response samples ──
	const responseArticles = `{
  "items": [
    {
      "id": 9876,
      "title": "Understanding Transformer Architectures",
      "link": "https://example.com/article",
      "description": "A practical deep dive into attention...",
      "thumbnail": null,
      "published_at": "2026-04-15T09:30:00Z",
      "category": "World Tech",
      "source": "Hacker News",
      "starred": false,
      "read": false,
      "has_full_content": true,
      "feed": {
        "id": 12,
        "name": "HN Frontpage",
        "url": "https://news.ycombinator.com/rss"
      },
      "content": "<div><p>Transformer models have become...</p></div>"
    }
  ],
  "pagination": {
    "limit": 5,
    "offset": 0,
    "total": 142,
    "has_more": true
  }
}`;

	const responseStream = `id: a12346-n678
event: article.created
data: {"id":12346,"title":"Zero-day in OpenSSL",
  "link":"https://example.com/openssl",
  "category":"World Tech","source":"Security Weekly",
  "starred":false,"read":false,"has_full_content":false,
  "feed":{"id":18,"name":"Security Weekly",
  "url":"https://example.com/rss"}}

id: a12346-n679
event: notification.created
data: {"id":679,"channel":"telegram",
  "kind":"article_batch",
  "title":"Security Weekly: 1 new article",
  "body":"New critical item detected",
  "link":"https://example.com/openssl",
  "article_id":12346,
  "sent_at":"2026-04-16T14:25:00Z"}`;

	const responseExtract = `{
  "item": {
    "id": 9876,
    "title": "Understanding Transformer Architectures",
    "has_full_content": true,
    "content": "<div><p>Transformer models have become...</p></div>"
  },
  "extraction": {
    "performed": true,
    "cached": false,
    "force_refresh": false
  }
}`;

	const endpoints = [
		{
			key: 'articles' as const,
			method: 'GET',
			methodColor: 'border-emerald-500/30 text-emerald-600 dark:text-emerald-400',
			path: '/api/external/articles',
			badges: [],
			summary: 'Query articles with filters — category, feed, starred, read status, pagination.',
			curl: curlArticles,
			python: pyArticles,
			response: responseArticles,
			responseLabel: 'Response'
		},
		{
			key: 'stream' as const,
			method: 'GET',
			methodColor: 'border-emerald-500/30 text-emerald-600 dark:text-emerald-400',
			path: '/api/external/stream',
			badges: [{ label: 'SSE', color: 'border-violet-500/30 text-violet-600 dark:text-violet-400' }],
			summary: 'Real-time Server-Sent Events stream of new articles and notifications.',
			curl: curlStream,
			python: pyStream,
			response: responseStream,
			responseLabel: 'Response (SSE events)'
		},
		{
			key: 'extract' as const,
			method: 'POST',
			methodColor: 'border-blue-500/30 text-blue-600 dark:text-blue-400',
			path: "/api/external/articles/{id}/extract",
			badges: [],
			summary: 'On-demand full-content extraction for a specific article.',
			curl: curlExtract,
			python: pyExtract,
			response: responseExtract,
			responseLabel: 'Response'
		}
	];
</script>

<div class="relative">
	<div
		class="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_60%_40%_at_50%_0%,rgba(99,102,241,0.08),transparent)]"
	></div>

	<div class="relative mx-auto max-w-5xl px-4 py-12 sm:px-6 lg:px-8 lg:py-20">
		<!-- Header -->
		<div class="mb-14 space-y-4">
			<div class="flex items-center gap-2">
				<Badge
					variant="outline"
					class="rounded-full border-primary/30 bg-primary/5 px-3 py-1 text-xs font-medium"
				>
					External API
				</Badge>
				<Badge
					variant="outline"
					class="rounded-full border-violet-500/30 bg-violet-500/5 px-3 py-1 text-xs font-medium text-violet-600 dark:text-violet-400"
				>
					REST + SSE
				</Badge>
			</div>
			<h1 class="text-3xl font-bold tracking-tight sm:text-4xl">
				API Documentation
			</h1>
			<p class="max-w-2xl text-base leading-relaxed text-muted-foreground">
				Newsy exposes a read-oriented REST API with Server-Sent Events streaming.
				Integrate curated feeds into trading bots, dashboards, research pipelines,
				or any downstream system.
			</p>
		</div>

		<!-- ── Overview cards ── -->
		<div class="mb-14 grid gap-4 sm:grid-cols-3">
			<Card class="rounded-2xl border-border/50 bg-card/80 p-5 shadow-sm">
				<div class="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
					<Settings class="size-4.5" />
				</div>
				<h3 class="mb-1 text-sm font-semibold">1. Enable the API</h3>
				<p class="text-xs leading-relaxed text-muted-foreground">
					Go to <span class="font-medium text-foreground">Settings &rarr; API</span> in your Newsy
					instance and toggle the external API on. This activates the
					<code class="rounded bg-muted px-1 py-0.5 text-[11px]">/api/external/*</code> routes.
				</p>
			</Card>
			<Card class="rounded-2xl border-border/50 bg-card/80 p-5 shadow-sm">
				<div class="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
					<Key class="size-4.5" />
				</div>
				<h3 class="mb-1 text-sm font-semibold">2. Generate a token</h3>
				<p class="text-xs leading-relaxed text-muted-foreground">
					On the same Settings &rarr; API page, click <span class="font-medium text-foreground">Generate Token</span>.
					Copy the token immediately &mdash; it won't be shown again.
					Tokens are scoped to your account.
				</p>
			</Card>
			<Card class="rounded-2xl border-border/50 bg-card/80 p-5 shadow-sm">
				<div class="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-violet-500/10 text-violet-600 dark:text-violet-400">
					<Shield class="size-4.5" />
				</div>
				<h3 class="mb-1 text-sm font-semibold">3. Authenticate requests</h3>
				<p class="text-xs leading-relaxed text-muted-foreground">
					Pass the token as a Bearer token in the <code class="rounded bg-muted px-1 py-0.5 text-[11px]">Authorization</code> header
					on every request:
				</p>
				<pre class="mt-2 overflow-x-auto rounded-lg bg-muted/40 px-3 py-2 font-mono text-[11px] leading-relaxed text-foreground/90">Authorization: Bearer YOUR_API_TOKEN</pre>
			</Card>
		</div>

		<!-- ── Setup + client overview ── -->
		<div class="mb-14 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
			<Card class="rounded-2xl border-border/50 bg-card/80 p-6 shadow-sm">
				<div class="mb-4 flex items-center gap-3">
					<div class="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
						<Settings class="size-4.5" />
					</div>
					<div>
						<h2 class="text-base font-semibold">Enable the API and generate a token</h2>
						<p class="text-xs text-muted-foreground">Everything starts in Settings → API</p>
					</div>
				</div>
				<ol class="space-y-3 text-sm leading-relaxed text-muted-foreground">
					{#each tokenSteps as step, index}
						<li class="flex gap-3">
							<span class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-foreground">
								{index + 1}
							</span>
							<span>{step}</span>
						</li>
					{/each}
				</ol>
			</Card>

			<Card class="rounded-2xl border-border/50 bg-card/80 p-6 shadow-sm">
				<div class="mb-4 flex items-center gap-3">
					<div class="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-500/10 text-violet-600 dark:text-violet-400">
						<Zap class="size-4.5" />
					</div>
					<div>
						<h2 class="text-base font-semibold">Included Python client</h2>
						<p class="text-xs text-muted-foreground">Repository example for real integrations</p>
					</div>
				</div>
				<ul class="space-y-3 text-sm leading-relaxed text-muted-foreground">
					{#each pythonClientSummary as item}
						<li class="flex gap-3">
							<span class="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary/60"></span>
							<span>{item}</span>
						</li>
					{/each}
				</ul>
				<div class="mt-4 rounded-lg bg-muted/40 p-3 font-mono text-[11px] leading-relaxed text-foreground/90">
					examples/python_external_api_client.py
				</div>
			</Card>
		</div>

		<!-- ── Endpoints ── -->
		<div class="mb-6 space-y-3">
			<div class="text-xs font-semibold tracking-[0.25em] text-muted-foreground uppercase">
				Endpoints
			</div>
			<h2 class="text-2xl font-bold tracking-tight sm:text-3xl">
				First-class REST + SSE interface
			</h2>
			<p class="max-w-2xl text-sm leading-relaxed text-muted-foreground">
				Every example below shows both <span class="font-medium text-foreground">curl</span> and
				<span class="font-medium text-foreground">Python</span> usage side by side,
				with realistic response structures from the real API shape.
			</p>
		</div>

		<div class="space-y-8">
			{#each endpoints as ep (ep.key)}
				<div class="overflow-hidden rounded-2xl border border-border/50 bg-card/80 shadow-sm">
					<!-- Endpoint header -->
					<div class="flex flex-wrap items-center gap-3 border-b border-border/40 bg-muted/20 px-5 py-3">
						<Badge variant="outline" class="rounded px-2 py-0.5 font-mono text-xs font-bold {ep.methodColor}">{ep.method}</Badge>
						<code class="text-sm font-medium">{ep.path}</code>
						{#each ep.badges as badge}
							<Badge variant="outline" class="ml-1 rounded px-1.5 py-0 text-[10px] {badge.color}">{badge.label}</Badge>
						{/each}
						<span class="ml-auto text-xs text-muted-foreground">{ep.summary}</span>
					</div>

					<!-- Tab bar -->
					<div class="flex border-b border-border/30 bg-muted/10">
						<button
							onclick={() => (activeTab[ep.key] = 'curl')}
							class="flex items-center gap-1.5 px-5 py-2.5 text-xs font-medium transition-colors {activeTab[ep.key] === 'curl'
								? 'border-b-2 border-primary text-foreground'
								: 'text-muted-foreground hover:text-foreground'}"
						>
							<Terminal class="size-3.5" />
							curl
						</button>
						<button
							onclick={() => (activeTab[ep.key] = 'python')}
							class="flex items-center gap-1.5 px-5 py-2.5 text-xs font-medium transition-colors {activeTab[ep.key] === 'python'
								? 'border-b-2 border-primary text-foreground'
								: 'text-muted-foreground hover:text-foreground'}"
						>
							<Zap class="size-3.5" />
							Python
						</button>
					</div>

					<!-- Code + response -->
					<div class="grid gap-0 lg:grid-cols-2">
						<div class="border-b border-border/30 p-5 lg:border-r lg:border-b-0">
							<div class="mb-2 text-xs font-medium text-muted-foreground">
								{activeTab[ep.key] === 'curl' ? 'Request (curl)' : 'Request (Python)'}
							</div>
							<pre class="overflow-x-auto rounded-lg bg-muted/40 p-4 font-mono text-xs leading-relaxed text-foreground/90"><code>{activeTab[ep.key] === 'curl' ? ep.curl : ep.python}</code></pre>
						</div>
						<div class="p-5">
							<div class="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
								<Server class="size-3.5" />
								{ep.responseLabel}
							</div>
							<pre class="overflow-x-auto rounded-lg bg-muted/40 p-4 font-mono text-xs leading-relaxed text-foreground/90"><code>{ep.response}</code></pre>
						</div>
					</div>
				</div>
			{/each}
		</div>

		<!-- ── Query parameters reference ── -->
		<div class="mt-14 space-y-4">
			<h2 class="text-xl font-bold tracking-tight">Query parameters</h2>
			<Card class="overflow-hidden rounded-2xl border-border/50 bg-card/80 p-0 shadow-sm">
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-border/40 bg-muted/20 text-left text-xs font-medium text-muted-foreground">
								<th class="px-5 py-3">Parameter</th>
								<th class="px-5 py-3">Endpoint</th>
								<th class="px-5 py-3">Type</th>
								<th class="px-5 py-3">Description</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-border/30">
							{#each [
								{ param: 'category', endpoint: 'articles, stream', type: 'string', desc: 'Filter by category name' },
								{ param: 'feed_url', endpoint: 'articles, stream', type: 'string', desc: 'Filter by exact feed URL' },
								{ param: 'q', endpoint: 'articles', type: 'string', desc: 'Case-insensitive search across title, description, and content' },
								{ param: 'since', endpoint: 'articles, stream', type: 'ISO timestamp', desc: 'Only return items published after the provided time' },
								{ param: 'starred', endpoint: 'articles', type: 'bool', desc: 'Only starred items' },
								{ param: 'include_content', endpoint: 'articles', type: 'bool', desc: 'Include full HTML content in response' },
								{ param: 'limit', endpoint: 'articles', type: 'int', desc: 'Max items to return (1..200)' },
								{ param: 'offset', endpoint: 'articles', type: 'int', desc: 'Pagination offset' },
								{ param: 'include_notifications', endpoint: 'stream', type: 'bool', desc: 'Include notification events in SSE stream' },
								{ param: 'force_refresh', endpoint: 'extract (body)', type: 'bool', desc: 'Re-extract even if content is already cached' },
							] as row}
								<tr>
									<td class="px-5 py-2.5"><code class="rounded bg-muted px-1.5 py-0.5 text-xs">{row.param}</code></td>
									<td class="px-5 py-2.5 text-xs text-muted-foreground">{row.endpoint}</td>
									<td class="px-5 py-2.5 font-mono text-xs text-muted-foreground">{row.type}</td>
									<td class="px-5 py-2.5 text-xs text-muted-foreground">{row.desc}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</Card>
		</div>

		<div class="mt-14 grid gap-4 lg:grid-cols-2">
			<Card class="rounded-2xl border-border/50 bg-card/80 p-6 shadow-sm">
				<h2 class="mb-2 text-base font-semibold">When to use curl</h2>
				<p class="text-sm leading-relaxed text-muted-foreground">
					Use curl examples for quick smoke tests, CI health checks, demos, and shell-based automation.
					They are the fastest way to verify auth, filters, extraction, and streaming behavior against a live instance.
				</p>
			</Card>
			<Card class="rounded-2xl border-border/50 bg-card/80 p-6 shadow-sm">
				<h2 class="mb-2 text-base font-semibold">When to use the Python client</h2>
				<p class="text-sm leading-relaxed text-muted-foreground">
					Use the bundled Python client as a starting point for ingestion workers, trading pipelines, and research daemons.
					It already demonstrates snapshot fetches, on-demand extraction, SSE streaming, and cursor persistence.
				</p>
			</Card>
		</div>

		<!-- Footer links -->
		<div class="mt-12 flex flex-wrap items-center justify-center gap-3">
			<Button
				href="https://github.com/krishna-vinci/newsy-selfhost/blob/main/docs/external-api.md"
				target="_blank"
				rel="noreferrer"
				variant="outline"
				class="gap-2"
			>
				<Github class="size-4" />
				Full API reference on GitHub
				<ArrowUpRight class="size-3.5" />
			</Button>
			<Button href="/landing" variant="ghost" class="text-muted-foreground">
				&larr; Back to home
			</Button>
		</div>
	</div>
</div>
