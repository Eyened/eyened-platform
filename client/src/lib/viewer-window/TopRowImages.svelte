<script lang="ts">
    import Spinner from "$lib/components/Spinner.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import TaskPanel from "$lib/tasks/TaskPanel.svelte";
    import { getContext } from "svelte";
    import TopViewer from "./TopViewer.svelte";
    import type { ViewerWindowContext } from "./viewerWindowContext.svelte";

    import { Button } from "$lib/components/ui/button";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import Add from "carbon-icons-svelte/lib/Add.svelte";
    import Help from "carbon-icons-svelte/lib/Help.svelte";
    import BrowserOverlay from "./BrowserOverlay.svelte";
    import HelpOverlay from "./HelpOverlay.svelte";

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );
    const taskContext = getContext<TaskContext>("taskContext");
    let selectedPanel: "browser" | "help" | null = $state(null);

    function selectPanel(panel: "browser" | "help" | null) {
        if (selectedPanel == panel) {
            selectedPanel = null;
        } else {
            selectedPanel = panel;
        }
    }
</script>

{#if viewerWindowContext.instanceIds.length == 0}
    <div class="empty">Enter instance IDs in url</div>
{:else}
    <div id="images">
        {#each viewerWindowContext.instanceIds as instanceId}
            {#await viewerWindowContext.getImages(instanceId)}
                <div class="itemLoading">
                    <div>Loading {instanceId}</div>
                    <Spinner />
                </div>
            {:then images}
                {#each images as image (image.image_id)}
                    <TopViewer {image} />
                {/each}
            {/await}
        {/each}
    </div>
    {#if taskContext}
        <TaskPanel {taskContext} />
    {/if}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <div
        id="panel"
        class:hidden={selectedPanel == null}
        tabindex="0"
        onpointerenter={(e) => e.target.focus()}
        onkeydown={(e) => {
            if (e.key == "Escape") {
                selectPanel(null);
            }
        }}
    >
        {#if selectedPanel !== "browser"}
            <div class="header">
                <Button
                    variant="outline"
                    size="sm"
                    onclick={() => selectPanel(null)}
                >
                    Close
                </Button>
            </div>
        {/if}
        <div class="panel-body">
            {#if selectedPanel == "browser"}
                <BrowserOverlay
                    {viewerWindowContext}
                    onClose={() => selectPanel(null)}
                />
            {/if}
            {#if selectedPanel == "help"}
                <HelpOverlay />
            {/if}
        </div>
    </div>
    <div id="panel-selector">
        <IconButton label="Help" onclick={() => selectPanel("help")}>
            <Help />
        </IconButton>
        <IconButton
            label="Browse images"
            onclick={() => selectPanel("browser")}
        >
            <Add />
        </IconButton>
    </div>
{/if}

<style>
    div.empty {
        padding: 2em;
        flex: 1;
        background-color: #000000;
        color: var(--color-text-primary);
        z-index: 2;
    }
    div.itemLoading {
        display: flex;
        flex: 1;
        flex-direction: column;
        align-items: center;
        flex-direction: column;
        background-color: black;
        border: 1px solid black;
        border-right: 1px solid gray;
        color: white;
        padding-top: 2em;
        z-index: 2;
    }

    div#panel-selector {
        z-index: 3;
        display: flex;
        flex: 0;
        flex-direction: column;
    }

    div#panel {
        position: fixed;
        z-index: 1000;
        left: 0;
        top: 0;
        bottom: 0;
        right: 0;
        background-color: var(--color-background);
        backdrop-filter: blur(10px);
        display: flex;
        flex-direction: column;
        /* The body scrolls, not the whole panel, so the header stays put */
        overflow: hidden;
        color: var(--color-text-primary);
    }
    div#panel.hidden {
        display: none !important;
    }
    div#panel .header {
        flex: 0 0 auto;
        display: flex;
        justify-content: right;
        padding: 0.2em;
    }
    div#panel .panel-body {
        flex: 1 1 auto;
        min-height: 0;
        display: flex;
        flex-direction: column;
        overflow-y: auto;
    }
    div#images {
        flex: 1;
        flex-direction: row;
        display: flex;
    }
</style>
