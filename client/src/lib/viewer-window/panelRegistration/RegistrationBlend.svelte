<script lang="ts">
    import { glslPathBetween } from "$lib/registration/glslPathBetween";
    import Viewer from "$lib/viewer/Viewer.svelte";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { ColorBlendRenderer } from "$lib/webgl/colorBlendRenderer";
    import { getContext, mount, unmount, untrack } from "svelte";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import { blendLayers, selectFixedImage } from "./blendLayers";

    interface Props {
        images: AbstractImage[];
    }

    let { images }: Props = $props();

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );

    const initialIds = untrack(() => images.map((image) => image.image_id));
    let fixedImageId = $state(initialIds[0] ?? "");
    let overlayImageIds = $state(initialIds.slice(1));

    const fixedImage = $derived(
        images.find((image) => image.image_id === fixedImageId) ?? null,
    );

    // ColorBlendRenderer uses private fields, so it stays a plain instance.
    // rendererEpoch is the signal that a new viewer context is ready.
    let blendRenderer: ColorBlendRenderer | null = null;
    let rendererEpoch = $state(0);

    let stage: HTMLDivElement | undefined = $state();

    function imageSize(id: string): [number, number] | undefined {
        for (const image of viewerWindowContext.topViewers.keys()) {
            if (image.image_id === id) return [image.width, image.height];
        }
        return undefined;
    }

    function chooseFixed(id: string) {
        const next = selectFixedImage({ fixedImageId, overlayImageIds }, id);
        fixedImageId = next.fixedImageId;
        overlayImageIds = next.overlayImageIds;
    }

    function setOverlay(id: string, checked: boolean) {
        if (checked) {
            if (!overlayImageIds.includes(id)) {
                overlayImageIds = [...overlayImageIds, id];
            }
            return;
        }
        overlayImageIds = overlayImageIds.filter((item) => item !== id);
    }

    // Viewer reads its context once. A new fixed image needs a new
    // ViewerContext, so the viewer is remounted rather than reused.
    $effect(() => {
        const node = stage;
        const image = fixedImage;
        if (!node || !image) return;

        const mounted = untrack(() => {
            const viewerContext = new ViewerContext(image, viewerWindowContext);
            const renderer = new ColorBlendRenderer(image.webgl);
            viewerContext.imageRenderer =
                renderer as unknown as typeof viewerContext.imageRenderer;
            const app = mount(Viewer, {
                target: node,
                props: { showInfo: false },
                intro: false,
                context: new Map<string, unknown>([
                    ["viewerContext", viewerContext],
                    ["viewerWindowContext", viewerWindowContext],
                ]),
            });
            blendRenderer = renderer;
            rendererEpoch += 1;
            return app;
        });

        return () => {
            const renderer = blendRenderer;
            blendRenderer = null;
            rendererEpoch += 1;
            unmount(mounted);
            renderer?.dispose();
        };
    });

    $effect(() => {
        const epoch = rendererEpoch;
        const renderer = blendRenderer;
        const fixedId = fixedImageId;
        const overlays = overlayImageIds;
        const ordered = images;
        const revision = viewerWindowContext.registration.revision;
        void epoch;
        void revision;
        if (!renderer || !fixedId) return;

        const byId = new Map(ordered.map((image) => [image.image_id, image]));
        const registration = viewerWindowContext.registration;
        const layers = blendLayers({
            orderedImageIds: ordered.map((image) => image.image_id),
            fixedImageId: fixedId,
            overlayImageIds: overlays,
            hasPath: (overlayId, fixed) =>
                glslPathBetween(registration, fixed, overlayId, imageSize) !==
                null,
            canSample: (imageId) => byId.get(imageId)?.is2D ?? false,
        });
        const drawn = [
            ...layers.filter((layer) => layer.draw && layer.role === "fixed"),
            ...layers.filter((layer) => layer.draw && layer.role === "overlay"),
        ];
        renderer.setLayers(
            drawn.flatMap((layer) => {
                const image = byId.get(layer.imageId);
                if (!image) return [];
                const mapping =
                    layer.role === "fixed"
                        ? null
                        : glslPathBetween(
                              registration,
                              fixedId,
                              layer.imageId,
                              imageSize,
                          );
                return [
                    {
                        texture: image.texture,
                        width: image.width,
                        height: image.height,
                        colour: layer.colour,
                        untinted: layer.untinted,
                        mapping,
                    },
                ];
            }),
        );
    });
</script>

<div class="blend">
    <div class="stage" bind:this={stage}></div>
    <aside class="controls">
        {#each images as image (image.image_id)}
            {@const id = image.image_id}
            <div class="control">
                <label>
                    <input
                        type="radio"
                        name="registration-fixed"
                        value={id}
                        checked={fixedImageId === id}
                        onchange={() => chooseFixed(id)}
                    />
                    {id}
                </label>
                {#if id !== fixedImageId}
                    <label>
                        <input
                            type="checkbox"
                            aria-label="Show {id}"
                            checked={overlayImageIds.includes(id)}
                            onchange={(event) =>
                                setOverlay(id, event.currentTarget.checked)}
                        />
                    </label>
                {/if}
            </div>
        {/each}
    </aside>
</div>

<style>
    .blend {
        flex: 1;
        min-height: 0;
        display: flex;
        flex-direction: row;
    }

    .stage {
        flex: 1;
        min-width: 0;
        min-height: 0;
        display: flex;
        position: relative;
    }

    .controls {
        flex: 0 0 auto;
        display: flex;
        flex-direction: column;
        gap: 0.35em;
        padding: 0.5em;
        overflow: auto;
        max-width: 16em;
        color: white;
    }

    .control {
        display: flex;
        align-items: center;
        gap: 0.5em;
    }

    label {
        display: flex;
        align-items: center;
        gap: 0.35em;
        min-width: 0;
    }
</style>
