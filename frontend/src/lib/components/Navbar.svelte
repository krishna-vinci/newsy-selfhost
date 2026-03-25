<script lang="ts">
    import * as NavigationMenu from "$lib/components/ui/navigation-menu/index.js";
    import { page } from "$app/stores";

    let { user = null } = $props();
</script>

<NavigationMenu.Root class="w-full max-w-full">
    <NavigationMenu.List class="flex w-full max-w-full items-center justify-start gap-2 overflow-x-auto rounded-lg bg-background p-1 shadow-sm sm:justify-center sm:p-2 sm:shadow-lg">
        <NavigationMenu.Item>
            <NavigationMenu.Link 
            href="/" 
            class="group inline-flex h-10 w-max shrink-0 items-center justify-center rounded-md bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground focus:outline-none disabled:pointer-events-none disabled:opacity-50 data-[active]:bg-accent/50 data-[state=open]:bg-accent/50"
            active={$page.url.pathname === '/'}
        >
            Home
        </NavigationMenu.Link>
    </NavigationMenu.Item>
    {#if user}
        <NavigationMenu.Item>
            <NavigationMenu.Link 
                href="/feeds" 
                class="group inline-flex h-10 w-max shrink-0 items-center justify-center rounded-md bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground focus:outline-none disabled:pointer-events-none disabled:opacity-50 data-[active]:bg-accent/50 data-[state=open]:bg-accent/50"
                active={$page.url.pathname === '/feeds'}
            >
                Feeds
            </NavigationMenu.Link>
        </NavigationMenu.Item>
		<NavigationMenu.Item>
		    <NavigationMenu.Link 
		        href="/reports" 
		        class="group inline-flex h-10 w-max shrink-0 items-center justify-center rounded-md bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground focus:outline-none disabled:pointer-events-none disabled:opacity-50 data-[active]:bg-accent/50 data-[state=open]:bg-accent/50"
		        active={$page.url.pathname === '/reports'}
		    >
		        Reports
		    </NavigationMenu.Link>
		</NavigationMenu.Item>
    {/if}
    </NavigationMenu.List>
</NavigationMenu.Root>
