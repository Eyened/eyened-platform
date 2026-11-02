<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import BulkTagger from "$lib/tags/BulkTagger.svelte";
    import Launch from "carbon-icons-svelte/lib/Launch.svelte";
    import { getContext } from "svelte";
    import type { BrowserContext } from "./browserContext.svelte";
    import { imageCount } from "./images";

    // Carbon data table batch action bar, sticky above the results toolbar (DESIGN.md deviation). In
    // overlay mode the selection is the sub-task's or viewer's images, so the bar can't clear or tag it.
    let {
        mode = "full",
        panelOpen,
        onviewselected,
    }: {
        mode?: "full" | "overlay";
        panelOpen: boolean;
        onviewselected: () => void;
    } = $props();

    const browserContext = getContext<BrowserContext>("browserContext");
    const action = "min-h-12 px-4 whitespace-nowrap [&>svg]:static";
</script>

<div
    class="sticky top-0 z-10 flex h-12 items-center overflow-x-auto bg-background-brand"
>
    <p
        class="sticky start-0 z-10 shrink-0 bg-background-brand px-4 text-body-compact-01 whitespace-nowrap text-text-on-color"
    >
        {imageCount(browserContext.selectedIds.length)} selected
    </p>
    <Button
        size="lg"
        class="{action} ms-auto"
        aria-expanded={panelOpen}
        aria-controls="selected-images"
        onclick={onviewselected}
    >
        View selected
    </Button>
    {#if mode === "full"}
        <Button
            size="lg"
            class={action}
            onclick={() => browserContext.openTab(browserContext.selectedIds)}
        >
            Open in viewer
            <Launch aria-hidden="true" />
        </Button>
        <BulkTagger
            instances={browserContext.selectedInstances}
            class={action}
        />
        <Button
            size="lg"
            class="{action} before:absolute before:start-0 before:top-4 before:h-4 before:w-px before:bg-text-on-color hover:before:opacity-0"
            onclick={() => (browserContext.selectedIds = [])}
        >
            Cancel
        </Button>
    {/if}
</div>
