<!--
@component
Main component for the viewer window.
Manages the layout of the viewer window.
Keeps track of the main panels and the top row of images.
-->
<script lang="ts">
    import type { TaskContext } from "$lib/types";
    import { getContext, onDestroy, onMount, setContext } from "svelte";
    import MainViewer from "./MainViewer.svelte";
    import { ViewerWindowContext } from "./viewerWindowContext.svelte";
    import TopRowImages from "./TopRowImages.svelte";
    import ViewerWindowInfoPanel from "./ViewerWindowInfoPanel.svelte";
    import MainPanel from "./MainPanel.svelte";
    import TaskTopBar from "$lib/tasks/TaskTopBar.svelte";

    interface Props {
        viewerWindowContext: ViewerWindowContext;
    }

    let { viewerWindowContext }: Props = $props();
    setContext("viewerWindowContext", viewerWindowContext);

    const taskContext = getContext<TaskContext>("taskContext");

    // open first image
    const { instanceIds } = viewerWindowContext;
    if ($instanceIds.length) {
        const openInstance = $instanceIds[0];
        viewerWindowContext.getImages(openInstance).then((images) => {
            // images is normally a single image
            // for OCT it is an array: enface projection + oct image
            const panel = {
                component: MainViewer,
                props: { image: images[images.length - 1] }, // last image (in case of OCT)
            };
            viewerWindowContext.setPanel(panel);
        });
    }

    let main: HTMLDivElement = $state();
    let isResizing = false;

    function startResize(event: PointerEvent) {
        isResizing = true;
        event.preventDefault();
    }

    function stopResize() {
        isResizing = false;
    }

    onMount(() => {
        if (window) {
            window.addEventListener("pointerup", stopResize);
            window.addEventListener("pointermove", doResize);
        }
    });

    onDestroy(() => {
        if (window) {
            window.removeEventListener("pointerup", stopResize);
            window.removeEventListener("pointermove", doResize);
        }
    });

    function doResize(e: PointerEvent) {
        if (!isResizing) {
            return;
        }
        main.style["grid-template-rows"] = `${e.clientY}px 1px 1fr`;
    }
</script>

{#if taskContext}
    <div id="task-row">
        <TaskTopBar />
    </div>
{/if}
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div id="main" bind:this={main}>
    <div id="top" class="row">
        <div id="top-images">
            <TopRowImages />
        </div>
        <div id="info">
            <ViewerWindowInfoPanel />
        </div>
    </div>
    <div id="resizer" onpointerdown={startResize}>
        <div id="handle" onpointerdown={startResize}><hr /></div>
    </div>
    <div id="main-viewer" class="row">
        {#if viewerWindowContext.mainPanels.length}
            {#each viewerWindowContext.mainPanels as panel (panel)}
                <MainPanel {viewerWindowContext} {panel}>
                    <panel.component {...panel.props} />
                </MainPanel>
            {/each}
        {:else}
            <div class="no-viewer">Select Image</div>
        {/if}
    </div>
</div>

<style>
    div.row {
        overflow: hidden;
    }
    div#task-row {
        color: rgba(255, 255, 255, 0.8);
        z-index: 1;
    }
    div#main {
        display: grid;
        grid-template-rows: 20% 1px 1fr;
        overflow: auto;
        flex: 1;
    }
    div#top {
        display: flex;
    }
    div#top-images {
        flex: 1;
        display: flex;
    }
    div#info {
        background-color: black;
        flex: 0;
        z-index: 1;
    }
    div#resizer {
        position: relative;
        background-color: gray;
    }
    div#handle {
        position: absolute;
        top: -3px;
        left: 50%;
        transform: translateX(-50%);
        width: 30px;
        height: 6px;
        background: #ccc;
        border-radius: 2px;
        border: 1px solid rgba(0, 0, 0, 0.3);
        cursor: row-resize;
        z-index: 100;
    }
    #handle hr {
        margin: 2px;

        border-top: 1px solid rgba(0, 0, 0, 0.4);
        background-color: rgba(255, 255, 255, 0.9);
    }
    div#main-viewer {
        display: flex;
    }

    div.no-viewer {
        background-color: gray;
        flex: 1;
        flex-direction: column;
        align-items: center;
        padding: 3em;
        z-index: 1;
    }
</style>
