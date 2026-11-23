<script lang="ts">
    // A strip tile's live image. Its controls moved: copy ID to 6, localizer lines to 2, projection to 4.
    // ASSUMPTION: only the drawing stays; the tile frame is ThumbnailStrip (plan decision 20).
    import Viewer from "$lib/viewer/Viewer.svelte";
    import { EnfaceProjectionOverlay } from "$lib/viewer/overlays/EnfaceProjectionOverlay";
    import { OCTLinesOverlay } from "$lib/viewer/overlays/OCTLinesOverlays";
    import { getContext, setContext } from "svelte";
    import type { ViewerWindowContext } from "./viewerWindowContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { resolveEnfaceOverlaySources } from "$lib/registration/resolveEnfaceOverlaySources";
    import { instances } from "$lib/data/stores.svelte";

    interface Props {
        image: AbstractImage;
    }

    let { image }: Props = $props();

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );

    const viewerContext = viewerWindowContext.topViewers.get(image)!;
    setContext("viewerContext", viewerContext);

    // resolveEnfaceOverlaySources reads registration.revision so this derived
    // re-runs when photo locators / registration sets import after mount.
    const resolved = $derived.by(() =>
        resolveEnfaceOverlaySources({
            imageId: image.image_id,
            imageWidth: image.width,
            imageHeight: image.height,
            registration: viewerWindowContext.registration,
            managers: viewerWindowContext.enfaceProjectionManagers,
            getImageSize: (id) => {
                for (const [img] of viewerWindowContext.topViewers) {
                    if (img.image_id === id) {
                        return [img.width, img.height];
                    }
                }
                if (id.endsWith("_proj")) {
                    const octId = id.slice(0, -"_proj".length);
                    const mgr =
                        viewerWindowContext.enfaceProjectionManagers.get(octId);
                    if (mgr) {
                        return [mgr.octImage.width, mgr.octImage.depth];
                    }
                }
                const meta = instances.get(id);
                if (meta) {
                    return [meta.columns, meta.rows];
                }
                return undefined;
            },
            projMode: viewerContext.enfaceProjectionMode,
            linkedModes: viewerContext.enfaceProjectionModesByOct,
        }),
    );
    const paintSources = $derived.by(() =>
        resolved.flatMap((source) => {
            const mainViewerContext = source.manager.mainViewerContext;
            return mainViewerContext ? [{ ...source, mainViewerContext }] : [];
        }),
    );

    let photoLocators = $derived(
        viewerWindowContext.photoLocators.get(image.image_id)!,
    );
    let hasLocators = $derived(
        image.is2D && photoLocators && photoLocators.length,
    );

    $effect(() => {
        if (hasLocators) {
            return viewerContext.addOverlay(new OCTLinesOverlay(photoLocators));
        }
    });

    $effect(() => {
        const sources = paintSources.filter((source) => source.mode !== "off");
        if (!sources.length) {
            return;
        }
        const overlay = new EnfaceProjectionOverlay(sources, image.webgl);
        const remove = viewerContext.addOverlay(overlay);
        return () => {
            remove();
            overlay.destroy();
        };
    });
</script>

<Viewer tabbable={false} />
