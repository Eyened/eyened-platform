<script lang="ts">
    import { getContext } from "svelte";
    import InstanceComponent from "./InstanceComponent.svelte";
    import type { BrowserContext } from "./browserContext.svelte";

    const browserContext = getContext<BrowserContext>("browserContext");

    function clear() {
        browserContext.selectedIds = [];
    }

    function openSelectionTab() {
        browserContext.openTab(browserContext.selectedIds);
    }
</script>

<div class="fixed bottom-0 left-0 right-0 w-full z-50 bg-black/90 text-white">
    <div class="flex gap-4 items-start p-2">
        <div class="button-container flex flex-col gap-1">
            <div>
                {browserContext.selectedIds.length}
                {browserContext.selectedIds.length != 1 ? "images" : "image"} selected
            </div>
            <button
                class="p-2 disabled:opacity-50"
                disabled={browserContext.selectedIds.length === 0}
                onclick={openSelectionTab}
            >
                Open selected images
            </button>
            <button
                class="p-2 disabled:opacity-50"
                disabled={browserContext.selectedIds.length === 0}
                onclick={clear}
            >
                Clear selection
            </button>
        </div>

        <div class="flex overflow-x-auto gap-2">
            {#each browserContext.selectedInstances as instance (instance.id)}
                <InstanceComponent {instance} />
            {/each}
        </div>
    </div>
</div>

<style>

</style>
