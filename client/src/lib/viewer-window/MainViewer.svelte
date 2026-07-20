<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
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

    import { formSchemas } from "$lib/data/stores.svelte";
    import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
    import { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
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
    import { FeaturePipetteOverlay } from "./panelSegmentation/FeaturePipetteOverlay";
    import EtdrsPanelHelp from "./panelHelp/EtdrsPanelHelp.svelte";
    import FormPanelHelp from "./panelHelp/FormPanelHelp.svelte";
    import InfoPanelHelp from "./panelHelp/InfoPanelHelp.svelte";
    import MeasurePanelHelp from "./panelHelp/MeasurePanelHelp.svelte";
    import RegistrationPanelHelp from "./panelHelp/RegistrationPanelHelp.svelte";
    import RenderingPanelHelp from "./panelHelp/RenderingPanelHelp.svelte";
    import SegmentationPanelHelp from "./panelHelp/SegmentationPanelHelp.svelte";
    interface Props {
        image: AbstractImage;
    }

    let { image }: Props = $props();

    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );
    const closePanel = getContext<() => void>("closePanel");

    const viewerContext = new ViewerContext(image, viewerWindowContext);
    setContext("viewerContext", viewerContext);

    const mainViewerContext = new MainViewerContext(
        viewerContext.instance.id,
        viewerContext.axis,
        viewerWindowContext,
        viewerContext.image,
    );
    setContext("mainViewerContext", mainViewerContext);
    onDestroy(viewerContext.addOverlay(mainViewerContext));
    onDestroy(
        viewerContext.addOverlay(
            new FeaturePipetteOverlay(mainViewerContext, globalContext.user.id),
        ),
    );

    const { activePanels } = viewerContext;
    // activePanels.add("Segmentation");

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

    const etdrsSchema = formSchemas.find(
        (schema) => schema.name === BUILTIN_VIEWER_FORM_SCHEMA_NAMES.ETDRS_GRID,
    )!;
    if (!etdrsSchema) {
        console.warn("ETDRS schema not found");
    }
    const registrationSchema = formSchemas.find(
        (schema) =>
            schema.name ===
            BUILTIN_VIEWER_FORM_SCHEMA_NAMES.POINTSET_REGISTRATION,
    )!;

    const panels: {
        name: PanelName;
        component: Component<Record<string, unknown>>;
        Icon: Component;
        Help?: Component;
        props?: Record<string, unknown>;
    }[] = [
        { name: "Info", component: PanelInfo, Icon: Info, Help: InfoPanelHelp },
        {
            name: "Rendering",
            component: PanelRendering,
            Icon: Rendering,
            Help: RenderingPanelHelp,
        },
    ];

    if (image.is2D && etdrsSchema) {
        panels.push({
            name: "ETDRS",
            component: PanelETDRS,
            Icon: ETDRS,
            Help: EtdrsPanelHelp,
            props: { etdrsSchema, active: false },
        });
    }

    if (image.is2D && registrationSchema) {
        panels.push({
            name: "Registration",
            component: PanelRegistration,
            Icon: Registration,
            Help: RegistrationPanelHelp,
            props: { registrationSchema, active: false },
        });
    }

    panels.push(
        {
            name: "Measure",
            component: PanelMeasure,
            Icon: Measure,
            Help: MeasurePanelHelp,
            props: { active: false },
        },
        { name: "Form", component: PanelForm, Icon: Form, Help: FormPanelHelp },
        {
            name: "Segmentation",
            component: PanelSegmentation,
            Icon: Draw,
            Help: SegmentationPanelHelp,
        },
    );
</script>

<div class="main">
    <section id="viewer" class="viewer-section">
        <Viewer />
    </section>
    <aside id="right" class="sidebar">
        <header id="close" class:vertical={minimize}>
            <button
                type="button"
                class="image-id-toggle"
                onclick={() => (minimize = !minimize)}
                aria-label="Toggle minimize"
            >
                <span class="image-id" class:minimize>
                    &#9660; <code class="image-id-text">[{image.image_id}]</code
                    >
                </span>
            </button>

            <MainIcon onclick={closePanel} tooltip="Close" Icon={Close} />

            {#if minimize}
                <MainIcon onclick={() => (minimize = false)} tooltip="Restore">
                    {#snippet iconSnippet()}
                        <span class="dots" aria-hidden="true">&#8942;</span>
                    {/snippet}
                </MainIcon>
            {/if}
        </header>

        <nav id="panels" class="panels" class:minimize>
            {#each panels as { name, component: Component, Icon, Help, props = { } }}
                <PanelHeader text={name} panelName={name} {Icon} {Help} />
                <section
                    class="panel {activePanels.has(name)
                        ? 'expanded'
                        : 'collapsed'}"
                >
                    <Component {...props} active={activePanels.has(name)} />
                </section>
            {/each}
        </nav>
    </aside>
</div>

<style>
    /* Base layout styles */
    .main {
        display: flex;
        flex-direction: row;
        flex: 1;
        color: rgba(255, 255, 255, 0.8);
    }

    .viewer-section {
        display: flex;
        flex: 1;
    }

    .sidebar {
        display: flex;
        flex-direction: column;
        flex: 0;
        background-color: black;
        border-right: 1px solid rgba(255, 255, 255, 0.4);
    }

    /* Header/Close section */
    header#close {
        display: flex;
        flex: 0;
        height: auto;
        user-select: none; /* Prevent selection of UI controls */
    }

    header#close.vertical {
        flex-direction: column;
    }

    button.image-id-toggle {
        display: flex;
        flex: 1;
        cursor: pointer;
        margin: auto;
        padding: 0;
        border: none;
        background: transparent;
        color: inherit;
        font: inherit;
        user-select: none; /* Button itself shouldn't be selectable */
    }

    .image-id {
        display: flex;
        flex: 1;
        font-size: 0.8em;
        align-items: center;
        justify-content: center;
    }

    .image-id.minimize {
        display: none;
    }

    /* Allow selection of the image ID text itself */
    code.image-id-text {
        user-select: text;
        font-family: inherit;
        font-size: inherit;
        background: transparent;
        padding: 0;
        border: none;
    }

    /* Panels navigation */
    nav.panels {
        display: flex;
        flex-direction: column;
        flex: 1;
        overflow-y: auto;
        overflow-x: hidden;
        padding-bottom: 4em;
    }

    nav.panels.minimize {
        display: none;
    }

    /* Panel sections */
    section.panel {
        display: flex;
        flex: 0;
        height: auto;
    }

    section.panel.collapsed {
        height: 0;
        overflow: hidden;
    }

    section.panel.expanded {
        background-color: rgba(255, 255, 255, 0.1);
        height: auto;
    }

    /* Icon dots */
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
        user-select: none; /* Icon shouldn't be selectable */
    }
</style>
