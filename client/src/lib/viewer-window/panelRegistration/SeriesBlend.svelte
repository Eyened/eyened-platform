<script lang="ts">
    import { instances } from "$lib/data";
    import { composeGlslPath } from "$lib/registration/composeGlslPath";
    import { glslPathBetween } from "$lib/registration/glslPathBetween";
    import Viewer from "$lib/viewer/Viewer.svelte";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { SeriesBlendRenderer } from "$lib/webgl/seriesBlendRenderer";
    import { UNMAPPED_LAYER } from "$lib/webgl/seriesBlendFragment";
    import { getContext, mount, unmount, untrack } from "svelte";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import { seriesBlendWeights } from "./seriesBlendWeights";

    interface Props {
        images: AbstractImage[];
    }

    let { images }: Props = $props();

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );

    const anchor = $derived(images[0] ?? null);

    let position = $state(0);
    let opacities = $state<Record<string, number>>({});

    // SeriesBlendRenderer uses private fields, so it stays a plain instance.
    // rendererEpoch is the signal that a new viewer context is ready.
    let blendRenderer: SeriesBlendRenderer | null = null;
    let rendererEpoch = $state(0);

    let stage: HTMLDivElement | undefined = $state();

    function opacityFor(imageId: string): number {
        return opacities[imageId] ?? 1;
    }

    function setOpacity(imageId: string, value: number) {
        opacities[imageId] = value;
    }

    function imageSize(imageId: string): [number, number] | undefined {
        for (const image of viewerWindowContext.topViewers.keys()) {
            if (image.image_id === imageId) {
                return [image.width, image.height];
            }
        }
        const instance = instances.get(imageId);
        if (instance && instance.columns > 0 && instance.rows > 0) {
            return [instance.columns, instance.rows];
        }
        return undefined;
    }

    // Viewer reads its context once. A new anchor image needs a new
    // ViewerContext, so the viewer is remounted rather than reused.
    $effect(() => {
        const node = stage;
        const image = anchor;
        if (!node || !image) return;

        const mounted = untrack(() => {
            const viewerContext = new ViewerContext(image, viewerWindowContext);
            const renderer = new SeriesBlendRenderer();
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
        const layers = images;
        const revision = viewerWindowContext.registration.revision;
        const seriesPosition = position;
        void epoch;
        void revision;
        if (!renderer || layers.length === 0) return;

        const anchorId = layers[0]!.image_id;
        const mappings = layers.map((image) => {
            if (image.image_id === anchorId) return composeGlslPath([]);
            return (
                glslPathBetween(
                    viewerWindowContext.registration,
                    anchorId,
                    image.image_id,
                    imageSize,
                ) ?? UNMAPPED_LAYER
            );
        });
        const weights = seriesBlendWeights(seriesPosition, layers.length).map(
            (weight, index) => weight * opacityFor(layers[index]!.image_id),
        );
        renderer.setLayers(layers, mappings);
        renderer.setWeights(weights);
    });
</script>

<div class="blend">
    <div class="stage" bind:this={stage}></div>
    <aside class="controls">
        <label class="series">
            Series
            <input
                type="range"
                min="0"
                max="1"
                step="0.001"
                value={position}
                aria-label="Series blend"
                title="Left is the first image. Moving right blends into each next image in turn."
                oninput={(event) =>
                    (position = Number(event.currentTarget.value))}
            />
        </label>
        {#each images as image (image.image_id)}
            <section class="layer">
                <div class="public-id" title={image.instance.id}>
                    {image.instance.id}
                </div>
                <label>
                    Opacity
                    <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.01"
                        value={opacityFor(image.image_id)}
                        aria-label="Opacity {image.instance.id}"
                        oninput={(event) =>
                            setOpacity(
                                image.image_id,
                                Number(event.currentTarget.value),
                            )}
                    />
                </label>
            </section>
        {/each}
    </aside>
</div>

<style>
    .blend {
        min-height: 0;
        height: 100%;
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
        width: 16em;
        color: white;
        background-color: rgba(0, 0, 0, 0.92);
    }

    .series,
    label {
        display: flex;
        align-items: center;
        gap: 0.4em;
        font-size: 0.8em;
    }

    .layer {
        display: flex;
        flex-direction: column;
        gap: 0.35em;
        padding: 0.4em;
        border: 1px solid rgba(255, 255, 255, 0.25);
    }

    .public-id {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-size: 0.85em;
    }

    input[type="range"] {
        flex: 1;
        min-width: 0;
    }
</style>
