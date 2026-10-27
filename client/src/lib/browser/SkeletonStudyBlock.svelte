<script lang="ts">
    import { skeleton } from "$lib/components/ui/table/skeleton.js";
    import { cn } from "$lib/utils.js";
    import { getContext } from "svelte";
    import type { BrowserContext } from "./browserContext.svelte";

    const size = getContext<BrowserContext>("browserContext").thumbnailSize;
</script>

<div class="bg-layer-01 p-4 pb-12 in-dialog:bg-layer-02">
    <span class={cn(skeleton, "mb-2 h-6 w-1/3")}></span>
    <span class={cn(skeleton, "h-4 w-1/2")}></span>
    <div
        class="mt-4 flex gap-2 border-t border-border-subtle-01 pt-4 in-dialog:border-border-subtle-02"
    >
        {#each { length: 3 }, i (i)}
            <span class={skeleton} style="width: {size}; height: {size};"
            ></span>
        {/each}
    </div>
</div>
