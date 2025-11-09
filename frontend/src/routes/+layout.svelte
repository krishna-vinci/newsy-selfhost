<script lang="ts">
  import "../app.css";
  import { ModeWatcher } from "mode-watcher";
  import { Toaster } from 'svelte-sonner';
  import Navbar from '$lib/components/Navbar.svelte';
  import SunIcon from "@lucide/svelte/icons/sun";
  import MoonIcon from "@lucide/svelte/icons/moon";

  import { toggleMode } from "mode-watcher";
  import Button from "$lib/components/ui/button/index.svelte";

  let { children } = $props();
</script>

<ModeWatcher />
<Toaster richColors />

<div class="flex flex-col h-screen">
  <header class="flex items-center justify-between p-4 border-b flex-shrink-0">
      <div class="flex-1">
          <a href="/" class="text-2xl font-bold">newsy</a>
      </div>
      <div class="flex-1 flex justify-center">
          <Navbar />
      </div>
      <div class="flex-1 flex justify-end">
          <Button onclick={toggleMode} variant="outline" size="icon">
              <SunIcon
               class="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 !transition-all dark:-rotate-90 dark:scale-0"
                  />
                  <MoonIcon
                   class="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 !transition-all dark:rotate-0 dark:scale-100"
                  />
                  <span class="sr-only">Toggle theme</span>
                 </Button>
          </div>
  </header>

  <div class="flex-1 overflow-hidden">
    {@render children?.()}
  </div>
</div>
