<script lang="ts">
    // A strip tile's live image. Its controls moved: copy ID to 6, localizer lines to 2, projection to 4.
    // ASSUMPTION: only the drawing stays; the tile frame is ThumbnailStrip (plan decision 20).
    import Viewer from "$lib/viewer/Viewer.svelte";
    import { OCTLinesOverlay } from "$lib/viewer/overlays/OCTLinesOverlays";
    import { getContext, setContext } from "svelte";
    import type { ViewerWindowContext } from "./viewerWindowContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import type { Workspace } from "$lib/workspace/workspace.svelte";

    interface Props {
        image: AbstractImage;
    }

    let { image }: Props = $props();

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );

    const workspace = getContext<Workspace>("workspace");

    const viewerContext = viewerWindowContext.topViewers.get(image)!;
    setContext("viewerContext", viewerContext);

    let photoLocators = $derived(
        viewerWindowContext.photoLocators.get(image.image_id)!,
    );
    let hasLocators = $derived(
        image.is2D && photoLocators && photoLocators.length,
    );

    $effect(() => {
        if (hasLocators) {
            return viewerContext.addOverlay(
                new OCTLinesOverlay(
                    photoLocators,
                    () => workspace.stripLocalizer,
                ),
            );
        }
    });
</script>

<Viewer tabbable={false} />
