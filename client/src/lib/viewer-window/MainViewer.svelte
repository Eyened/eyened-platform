<script lang="ts">
    import {
        CLIENT_DEFAULTS,
        mergeClientConfig,
    } from "$lib/config/clientDefaults";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import SliceScrollbar from "$lib/viewer/SliceScrollbar.svelte";
    import ViewControls from "$lib/viewer/ViewControls.svelte";
    import type { ViewerEvent } from "$lib/viewer/viewer-utils";
    import Viewer from "$lib/viewer/Viewer.svelte";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { getContext, onDestroy, setContext, untrack } from "svelte";
    import { ViewerWindowContext } from "./viewerWindowContext.svelte";

    import { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import { FeaturePipetteOverlay } from "./panelSegmentation/FeaturePipetteOverlay";
    import { pointArming } from "$lib/forms/pointArming.svelte";
    import { PointTool } from "$lib/viewer/tools/PointTool.svelte";
    import { MeasureTool } from "$lib/viewer/tools/Measure.svelte";
    import { createViewTool } from "$lib/viewer/tools/viewTools";
    import { GridLayers } from "$lib/layers/gridLayers.svelte";
    import type {
        LayersTarget,
        Workspace,
    } from "$lib/workspace/workspace.svelte";
    interface Props {
        image: AbstractImage;
    }

    let { image }: Props = $props();

    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );

    const viewerContext = new ViewerContext(image, viewerWindowContext);
    setContext("viewerContext", viewerContext);

    const taskContext = getContext<TaskContext | undefined>("taskContext");
    viewerContext.renderControls = !mergeClientConfig(
        CLIENT_DEFAULTS,
        taskContext?.task.task_definition.config,
    ).layout.hide.includes("Rendering");

    const mainViewerContext = new MainViewerContext(
        viewerContext.instance.id,
        viewerContext.axis,
        viewerWindowContext,
        viewerContext.image,
    );
    setContext("mainViewerContext", mainViewerContext);
    onDestroy(viewerContext.addOverlay(mainViewerContext));
    // Layers' state for this viewport lives here, because Layers remounts its sections when the selection moves.
    const layers: LayersTarget = {
        viewerContext,
        mainViewerContext,
        grids: new GridLayers(viewerContext, viewerWindowContext.registration),
        measure: new MeasureTool(viewerContext.image),
    };

    if (image.is3D) {
        const enfaceManager = viewerWindowContext.enfaceProjectionManagers.get(
            image.instance.id,
        );
        enfaceManager?.registerMainViewerContext(mainViewerContext);
    }

    onDestroy(
        viewerContext.addOverlay(
            new FeaturePipetteOverlay(mainViewerContext, globalContext.user.id),
        ),
    );

    const topViewer = viewerWindowContext.topViewers.get(image)!;

    // The tile's zoom on hover, as a multiple of its own fit.
    const TWIN_ZOOM = 3;

    const followCursor = {
        pointermove(e: ViewerEvent<PointerEvent>) {
            if (!viewerWindowContext.viewState.stripTracking) return;
            const p = e.viewerContext.viewerToImageCoordinates(e.cursor);
            topViewer.focusFromFit(p.x, p.y, TWIN_ZOOM);
        },
        pointerleave() {
            topViewer.initTransform();
        },
    };

    onDestroy(viewerContext.addOverlay(followCursor));

    // Switching Crosshair tracking off returns the tile to its fit.
    $effect(() => {
        if (!viewerWindowContext.viewState.stripTracking)
            untrack(() => topViewer.initTransform());
    });
    onDestroy(() => {
        topViewer.initTransform();
    });

    const workspace = getContext<Workspace>("workspace");

    // The armed view tool acts in every viewport; strip tiles never take it.
    $effect(() => {
        const tool = createViewTool(workspace.armedTool);
        if (!tool) return;
        const remove = viewerContext.addOverlay(tool);
        return () => {
            remove();
            viewerContext.resetCursor();
        };
    });

    // Reset view and the options bar act on the selected viewport through this handle.
    const position = getContext<(() => number) | undefined>("viewportPosition");
    $effect(() => {
        if (!position) return;
        return workspace.attachViewport(position(), {
            get zoomPercent() {
                return Math.round(viewerContext.transform.scale * 100);
            },
            zoomBy(factor: number) {
                const { width, height } = viewerContext.viewerSize;
                viewerContext.zoom(width / 2, height / 2, factor);
            },
            reset: () => viewerContext.initTransform(),
            layers,
        });
    });

    // Form PointField: mount PointTool while a session is armed. Live SoT is
    // session.fieldValue — do not remount when it changes (only on session key).
    $effect(() => {
        const session = pointArming.session;
        if (!session) return;
        const sessionKey = session.key;
        const { analysis } = session;
        void sessionKey;

        const publicId = () => viewerContext.image.instance.id;

        const tool = new PointTool({
            canEdit: session.canEdit,
            label: session.label ?? "Point",
            pointStyle: session.pointStyle,
            radius: session.radius,
            color: session.color,
            cardinality: analysis.cardinality,
            sparse: analysis.sparse,
            coordinateSpace: analysis.coordinateSpace,
            enumExtras: analysis.enumExtras,
            onChange: (points) => {
                session.setPoints(publicId(), points);
            },
            onPersist: (points) => {
                session.setPoints(publicId(), points);
                session.persist();
            },
        });

        const remove = viewerContext.addOverlay(tool);

        // Keep tool.points in sync with session (PointField edits, other viewers).
        const stopSync = $effect.root(() => {
            $effect(() => {
                tool.points = session.getPoints(publicId());
            });
        });

        return () => {
            stopSync();
            tool.destroy();
            remove();
        };
    });
</script>

<div class="main">
    <!-- ASSUMPTION: the sidebar is removed, not hidden, so the panel header component can be deleted (plan decision 12). -->
    <section
        class="viewer-section"
        class:has-bar={viewerContext.renderControls}
    >
        <Viewer />
        {#if image.is3D && image.depth > 1}
            <SliceScrollbar />
        {/if}
        <ViewControls />
    </section>
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
        position: relative;
        display: flex;
        flex: 1;
        min-width: 0;
    }
    /* The bar sits below the image, so it never covers part of the retina. */
    .viewer-section.has-bar {
        padding-bottom: 2rem;
    }
</style>
