<!--
@component
The Magnifier's view of one source viewport: its own viewer on the same image, centred on the pointer.
Mount it keyed on the source viewport.
-->
<script lang="ts">
    import {
        MagnifierCopy,
        MagnifierMark,
    } from "$lib/viewer/overlays/magnifierOverlays";
    import type { Overlay } from "$lib/viewer/viewer-utils";
    import Viewer from "$lib/viewer/Viewer.svelte";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext, onDestroy, setContext, untrack } from "svelte";
    import type { MagnifierSource } from "./magnifier";
    import type { Workspace } from "./workspace.svelte";

    let { source }: { source: MagnifierSource } = $props();

    const workspace = getContext<Workspace>("workspace");
    // Keyed on the source viewport, so it never changes while mounted.
    const from = untrack(() => source.viewerContext);
    const view = new ViewerContext(from.image, from.viewerWindowContext);
    // The pointer is over the source, so the shared crosshair stays out of the panel; the mark shows the centre.
    view.active = true;
    setContext("viewerContext", view);

    // Holding H over the source hides these; the copied image stays.
    const unlessHidden = (overlay: Overlay): Overlay => ({
        repaint: (v, target) => {
            if (!from.hideOverlays) overlay.repaint(v, target);
        },
    });
    const BRUSHES = ["brush", "eraser", "enhance"];
    onDestroy(
        view.addOverlay(unlessHidden(untrack(() => source.mainViewerContext))),
    );
    onDestroy(
        view.addOverlay(
            unlessHidden(
                new MagnifierMark(() =>
                    BRUSHES.includes(workspace.armedTool ?? "")
                        ? {
                              radius: source.mainViewerContext
                                  .segmentationContext.brushRadius,
                              dashed: workspace.armedTool === "eraser",
                          }
                        : null,
                ),
            ),
        ),
    );
    // After the source's repaint, which draws the segmentation masks into the shared WebGL canvas, so the copy includes them.
    onDestroy(view.addOverlay(new MagnifierCopy()));

    $effect(() => {
        view.index = from.index;
        view.renderMode = from.renderMode;
        view.windowLevel = { ...from.windowLevel };
        view.stretch = from.stretch;
        view.focusFrom(from, source.x, source.y, workspace.magnifier.zoom);
    });
</script>

<Viewer tabbable={false} />
