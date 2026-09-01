<!--
@component
Main component for the viewer window.
Manages the layout of the viewer window.
Keeps track of the main panels and the top row of images.
-->
<script lang="ts">
    import { onDestroy, onMount, setContext } from "svelte";
    import MainPanel from "./MainPanel.svelte";
    import TopRowImages from "./TopRowImages.svelte";
    import { ViewerWindowContext } from "./viewerWindowContext.svelte";
    import RegistrationItemLoader from "./RegistrationItemLoader.svelte";
    import { instances, patients } from "$lib/data";
    import type { RegistrationSet } from "$lib/registration/registrationItem";
    import { collectPatientRegistrationSets } from "$lib/registration/registrationItem";

    interface Props {
        viewerWindowContext: ViewerWindowContext;
    }

    let { viewerWindowContext }: Props = $props();
    setContext("viewerWindowContext", viewerWindowContext);
    const registration = viewerWindowContext.registration;

    // Main viewers are restored by ViewerWindowContext after images load
    // (see restoreMainViewersFromViewState) so task grade and /view share one path.

    let main: HTMLDivElement | undefined = $state();
    let isResizing = false;
    let registrationSet: RegistrationSet[] = $derived.by(() => {
        const result: RegistrationSet[] = [];
        const patientIds = new Set<number>(
            viewerWindowContext.instanceIds
                .map((id) => instances.get(id)?.patient.id)
                .filter((pid): pid is number => typeof pid === "number"),
        );
        // TODO: check if patient can be fetched with promise directly?
        for (const patientId of patientIds) {
            const patient = patients.get(patientId);
            result.push(...collectPatientRegistrationSets(patient?.attrs));
        }
        return result;
    });

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
        if (!main) return;
        main.style.setProperty("grid-template-rows", `${e.clientY}px 1px 1fr`);
    }
</script>

<!-- Patient attrs first, then form pointset/affine (pointset wins on conflict). -->
<RegistrationItemLoader {registration} {registrationSet} />

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div id="main" bind:this={main} class="dark">
    <div id="top" class="row">
        <TopRowImages />
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
