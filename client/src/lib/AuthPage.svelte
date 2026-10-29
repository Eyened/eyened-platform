<script lang="ts">
    import type { Snippet } from "svelte";

    let { children }: { children: Snippet } = $props();
</script>

<!-- Carbon Login pattern, one step, centred. -->
<main class="flex flex-1 justify-center overflow-y-auto px-4">
    <div class="my-auto w-full max-w-80 py-16">
        {@render children()}
    </div>
</main>
