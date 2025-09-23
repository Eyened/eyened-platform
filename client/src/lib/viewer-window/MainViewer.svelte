<script lang="ts">
    import type { TaskContext } from "$lib/types";
    import type { PanelName, ViewerEvent } from "$lib/viewer/viewer-utils";
    import Viewer from "$lib/viewer/Viewer.svelte";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { getContext, onDestroy, setContext, type Component } from "svelte";
    import MainIcon from "./icons/MainIcon.svelte";
    import PanelETDRS from "./panelETRDS/PanelETDRS.svelte";
    import PanelForm from "./panelForm/PanelForm.svelte";
    import PanelHeader from "./PanelHeader.svelte";
    import PanelMeasure from "./panelMeasure/PanelMeasure.svelte";
    import PanelRegistration from "./panelRegistration/PanelRegistration.svelte";
    import PanelRendering from "./panelRendering/PanelRendering.svelte";
    import { ViewerWindowContext } from "./viewerWindowContext.svelte";

    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { data } from "$lib/datamodel/model";
    import { SegmentationOverlay } from "$lib/viewer/overlays/SegmentationOverlay.svelte";
    import {
        Close,
        Draw,
        ETDRS,
        Form,
        Info,
        Registration,
        Rendering,
    } from "./icons/icons";
    import Measure from "./icons/Measure.svelte";
    import PanelInfo from "./panelInfo/panelInfo.svelte";
    import PanelSegmentation from "./panelSegmentation/PanelSegmentation.svelte";
    interface Props {
        image: AbstractImage;
    }

    let { image }: Props = $props();

    const taskContext = getContext<TaskContext>("taskContext");
    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );
    const { registration } = viewerWindowContext;
    const closePanel = getContext<() => {}>("closePanel");

    const viewerContext = new ViewerContext(image, registration);
    setContext("viewerContext", viewerContext);

    const globalContext = getContext<GlobalContext>("globalContext");
    const segmentationOverlay = new SegmentationOverlay(viewerContext, globalContext);
    setContext("segmentationOverlay", segmentationOverlay);    
    onDestroy(viewerContext.addOverlay(segmentationOverlay));

    const { activePanels } = viewerContext;
    activePanels.add("Segmentation");

    const topViewer = viewerWindowContext.topViewers.get(image)!;

    const followCursor = {
        pointermove(e: ViewerEvent<PointerEvent>) {
            const { viewerContext } = e;
            const { x, y } = e.cursor;
            const { viewerSize } = viewerContext;
            const p = viewerContext.viewerToImageCoordinates({ x, y });
            const scaleH = viewerSize.height / image.height;
            const scaleW = viewerSize.width / image.width;
            const baseFactor = Math.min(scaleH, scaleW);
            const factor = image.is3D
                ? 0.4
                : image.image_id.endsWith("_proj")
                  ? 0.5
                  : 5;
            topViewer.focusPoint(p.x, p.y, factor * baseFactor);
        },
        pointerleave() {
            topViewer.initTransform();
        },
    };

    onDestroy(viewerContext.addOverlay(followCursor));
    onDestroy(() => {
        topViewer.initTransform();
    });

    let minimize = $state(viewerWindowContext.mainPanels.length > 1);

    const { formSchemas } = data;
    const etdrsSchema = formSchemas.find(
        (schema) => schema.name === "ETDRS-grid coordinates",
    )!;
    if (!etdrsSchema) {
        console.warn("ETDRS schema not found");
    }
    const registrationSchema = formSchemas.find(
        (schema) => schema.name === "Pointset registration",
    )!;

    const panels: { name: PanelName, component: Component, Icon: Component, props?: any }[] = [
        { name: "Info", component: PanelInfo, Icon: Info },
        {
            name: "Rendering",
            component: PanelRendering,
            Icon: Rendering,
        },
    ];

    if (image.is2D && etdrsSchema) {
        panels.push({
            name: "ETDRS",
            component: PanelETDRS,
            Icon: ETDRS,
            props: { etdrsSchema, active: false },
        });
    }

    if (image.is2D && registrationSchema) {
        panels.push({
            name: "Registration",
            component: PanelRegistration,
            Icon: Registration,
            props: { registrationSchema, active: false },
        });
    }

    panels.push(
        {
            name: "Measure",
            component: PanelMeasure,
            Icon: Measure,
            props: { active: false },
        },
        { name: "Form", component: PanelForm, Icon: Form },
        {
            name: "Segmentation",
            component: PanelSegmentation,
            Icon: Draw,
        },
    );
</script>


<div class="main">
    <div id="viewer">
        <Viewer />
    </div>
    <div id="right">
        <div id="close" class:vertical={minimize}>
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <span
                class="image-id"
                onclick={() => (minimize = !minimize)}
                class:minimize
            >
                &#9660; [{image.image_id}]
            </span>

            <MainIcon onclick={closePanel} tooltip="Close" Icon={Close} />

            {#if minimize}
                <MainIcon onclick={() => (minimize = false)} tooltip="minimize">
                    {#snippet iconSnippet()}
                        <span class="dots">&#8942;</span>
                    {/snippet}
                </MainIcon>
            {/if}
        </div>

        <div id="panels" class:minimize>
            {#each panels as { name, component: Component, Icon, props = { } }}
                <PanelHeader text={name} panelName={name} {Icon} />
                <div
                    class="panel {activePanels.has(name)
                        ? 'expanded'
                        : 'collapsed'}"
                >
                    <Component {...props} active={activePanels.has(name)} />
                </div>
            {/each}
        </div>
    </div>
</div>

<style>
    div {
        display: flex;
        flex: 1;
        user-select: none;
        color: rgba(255, 255, 255, 0.8);
    }

    div.vertical {
        flex-direction: column;
    }

    .minimize {
        display: none;
    }

    div.main {
        flex-direction: row;
    }

    div#viewer {
        flex: 1;
    }

    div#panels {
        flex-direction: column;
        flex: 1;
        overflow-y: auto;
        overflow-x: hidden;
        padding-bottom: 4em;
    }

    div#right {
        flex-direction: column;
        flex: 0;
        background-color: black;
        border-right: 1px solid rgba(255, 255, 255, 0.4);
    }

    div#close,
    div.panel {
        height: auto;
        flex: 0;
    }

    span.image-id {
        display: flex;
        flex: 1;
        cursor: pointer;
        margin: auto;
        font-size: 0.8em;
    }

    span.image-id.minimize {
        display: none;
    }

    .panel.collapsed {
        height: 0;
        overflow: hidden;
    }

    .panel.expanded {
        background-color: rgba(255, 255, 255, 0.1);
        height: auto;
    }

    span.dots {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0.2em;
        width: 1.5em;
        height: 1.5em;
        margin: auto;
        border: 1px solid rgba(255, 255, 255, 0.5);
        border-radius: 50%;
        font-weight: bold;
    }
</style>
