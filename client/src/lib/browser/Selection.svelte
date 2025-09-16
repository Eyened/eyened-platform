<script lang="ts">
    import { getContext } from "svelte";
    import InstanceComponent from "./InstanceComponent.svelte";

    import { data } from "$lib/datamodel/model";
    import type { BrowserContext } from "./browserContext.svelte";

    const browserContext = getContext<BrowserContext>("browserContext");
    const { instances } = data;

    function clear() {
        browserContext.selection = [];
    }

    function openSelectionTab() {
        browserContext.openTab(browserContext.selection);
    }
</script>

<div class="flex bg-black text-white">
    <div class="button-container flex flex-col p-2">
        <div>
            {browserContext.selection.length}
            {browserContext.selection.length != 1 ? "images" : "image"} selected
        </div>
        <button
            class="p-2"
            disabled={browserContext.selection.length === 0}
            onclick={openSelectionTab}
        >
            Open selected images
        </button>
        <button
            class="p-2"
            disabled={browserContext.selection.length === 0}
            onclick={clear}
        >
            Clear selection
        </button>
    </div>
    <div>
        {#each browserContext.selection as instanceId (instanceId)}
            <InstanceComponent instance={instances.get(instanceId)!} />
        {/each}
    </div>
</div>

<style>

</style>
