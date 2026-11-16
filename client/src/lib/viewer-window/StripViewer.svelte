<script lang="ts">
    // A strip tile's live image only; the tile frame and its Copy public ID bar are ThumbnailStrip's.
    import Viewer from "$lib/viewer/Viewer.svelte";
    import { NoEditCursor } from "$lib/viewer/tools/viewTools";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import { getContext, setContext } from "svelte";
    import type { ViewerWindowContext } from "./viewerWindowContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";

    interface Props {
        image: AbstractImage;
    }

    let { image }: Props = $props();

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );

    const viewerContext = viewerWindowContext.topViewers.get(image)!;
    setContext("viewerContext", viewerContext);
    const workspace = getContext<Workspace>("workspace");
    // A strip tile never takes points.
    $effect(() => {
        if (workspace.armedTool !== "point") return;
        const remove = viewerContext.addOverlay(new NoEditCursor());
        return () => {
            remove();
            viewerContext.resetCursor();
        };
    });
</script>

<Viewer tabbable={false} />
