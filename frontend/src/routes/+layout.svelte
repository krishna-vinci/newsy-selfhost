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

<div class="absolute top-4 right-4">
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

<Navbar />

{@render children?.()}
