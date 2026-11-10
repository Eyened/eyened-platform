<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { ViewerEvent } from "$lib/viewer/viewer-utils";
    import Viewer from "$lib/viewer/Viewer.svelte";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { getContext, onDestroy, setContext } from "svelte";
    import { ViewerWindowContext } from "./viewerWindowContext.svelte";

    import { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import { FeaturePipetteOverlay } from "./panelSegmentation/FeaturePipetteOverlay";
    import { pointArming } from "$lib/forms/pointArming.svelte";
    import { PointTool } from "$lib/viewer/tools/PointTool.svelte";
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

    const mainViewerContext = new MainViewerContext(
        viewerContext.instance.id,
        viewerContext.axis,
        viewerWindowContext,
        viewerContext.image,
    );
    setContext("mainViewerContext", mainViewerContext);
    onDestroy(viewerContext.addOverlay(mainViewerContext));

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
    <section class="viewer-section">
        <Viewer />
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
        display: flex;
        flex: 1;
        min-width: 0;
    }
</style>
