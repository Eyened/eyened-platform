<script lang="ts">
    import { glslPathBetween } from "$lib/registration/glslPathBetween";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { UNMAPPED_LAYER } from "$lib/webgl/blendFragment";
    import {
        BlendRenderer,
        type BlendLayerStyle,
    } from "$lib/webgl/blendRenderer";
    import { getContext, untrack } from "svelte";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import BlendLayerControls from "./BlendLayerControls.svelte";
    import {
        defaultBlendStyle,
        mountBlendViewer,
        registeredImageSize,
    } from "./blendViewer";
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
    let styles = $state<Record<string, BlendLayerStyle>>({});

    $effect.pre(() => {
        for (const image of images) {
            if (!untrack(() => styles[image.image_id])) {
                styles[image.image_id] = defaultBlendStyle("#ffffff", 0);
            }
        }
    });

    // Raw, because BlendRenderer uses private fields.
    let blendRenderer = $state.raw<BlendRenderer | null>(null);
    let stage: HTMLDivElement | undefined = $state();

    $effect(() => {
        const node = stage;
        const image = anchor;
        if (!node || !image) return;
        const renderer = new BlendRenderer();
        const unmountViewer = untrack(() =>
            mountBlendViewer(node, image, viewerWindowContext, renderer),
        );
        blendRenderer = renderer;
        return () => {
            blendRenderer = null;
            unmountViewer();
            renderer.dispose();
        };
    });

    // Paths follow registration only, so the sliders do not re-bake them.
    const mappings = $derived.by(() => {
        void viewerWindowContext.registration.revision;
        const anchorId = images[0]?.image_id;
        return images.map(
            (image) =>
                (anchorId &&
                    glslPathBetween(
                        viewerWindowContext.registration,
                        anchorId,
                        image.image_id,
                        (id) => registeredImageSize(viewerWindowContext, id),
                    )) ||
                UNMAPPED_LAYER,
        );
    });

    $effect(() => {
        const renderer = blendRenderer;
        const layers = images;
        if (!renderer || layers.length === 0) return;

        const weights = seriesBlendWeights(position, layers.length);
        renderer.setLayers(
            layers.map((image, index) => ({
                image,
                mapping: mappings[index] ?? UNMAPPED_LAYER,
                style:
                    $state.snapshot(styles[image.image_id]) ??
                    defaultBlendStyle("#ffffff", 0),
                weight: weights[index]!,
            })),
        );
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
            {#if styles[image.image_id]}
                <BlendLayerControls
                    {image}
                    name={image.instance.id}
                    bind:style={styles[image.image_id]}
                />
            {/if}
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

    .series {
        display: flex;
        align-items: center;
        gap: 0.4em;
        font-size: 0.8em;
    }

    input[type="range"] {
        flex: 1;
        min-width: 0;
    }
</style>
