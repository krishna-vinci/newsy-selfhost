<script lang="ts">
  import "../app.css";
  import { ModeWatcher } from "mode-watcher";
  import { Toaster } from 'svelte-sonner';
  import Navbar from '$lib/components/Navbar.svelte';
  import SunIcon from "@lucide/svelte/icons/sun";
  import MoonIcon from "@lucide/svelte/icons/moon";

  import { toggleMode } from "mode-watcher";
  import Button from "$lib/components/ui/button/index.svelte";

  let { children, data } = $props();

</script>

<ModeWatcher />
<Toaster richColors />

<div class="flex h-screen flex-col">
  <header class="border-b px-4 py-3 flex-shrink-0 sm:px-6">
      <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div class="flex items-center justify-between gap-3 md:flex-1">
              <a href="/" class="text-xl font-bold sm:text-2xl">newsy</a>
              <Button onclick={toggleMode} variant="outline" size="icon" class="md:hidden">
                   <SunIcon
                    class="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 !transition-all dark:-rotate-90 dark:scale-0"
                      />
                      <MoonIcon
                       class="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 !transition-all dark:rotate-0 dark:scale-100"
                      />
                      <span class="sr-only">Toggle theme</span>
              </Button>
          </div>

          <div class="order-3 md:order-2 md:flex-1 md:px-4">
              <Navbar user={data.auth.user} />
          </div>

          <div class="order-2 flex flex-wrap items-center gap-2 md:order-3 md:flex-1 md:justify-end">
              {#if !data.auth.isAuthenticated && !data.auth.bootstrapRequired}
                  <Button href="/login" variant="outline" class="flex-1 sm:flex-none">
                      Login
                  </Button>
                  {#if data.auth.allowPublicSignup}
                      <Button href="/signup" class="flex-1 sm:flex-none">
                          Sign up
                      </Button>
                  {/if}
              {/if}
              <Button onclick={toggleMode} variant="outline" size="icon" class="hidden md:inline-flex">
                   <SunIcon
                    class="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 !transition-all dark:-rotate-90 dark:scale-0"
                      />
                      <MoonIcon
                       class="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 !transition-all dark:rotate-0 dark:scale-100"
                      />
                      <span class="sr-only">Toggle theme</span>
              </Button>
          </div>
      </div>
  </header>

  <div class="relative flex-1 overflow-hidden">
    {@render children?.()}
  </div>
</div>
