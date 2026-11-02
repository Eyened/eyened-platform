<script lang="ts">
    import { composeGlslPath } from "$lib/registration/composeGlslPath";
    import { glslPathBetween } from "$lib/registration/glslPathBetween";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import {
        BlendRenderer,
        type BlendComposite,
        type BlendLayer,
        type BlendMapping,
    } from "$lib/webgl/blendRenderer";
    import { getContext, untrack } from "svelte";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import BlendLayerControls from "./BlendLayerControls.svelte";
    import {
        defaultBlendStyle,
        mountBlendViewer,
        registeredImageSize,
    } from "./blendViewer";
    import { directAffineMatrix } from "./directAffine";

    interface Props {
        images: AbstractImage[];
    }

    let { images }: Props = $props();

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );

    const fixedMapping = composeGlslPath([]);
    const fixedImage = $derived(images[0] ?? null);
    const movingImage = $derived(images[1] ?? null);

    let composite = $state<BlendComposite>("overlay");
    let tile = $state(64);
    let fixedStyle = $state(defaultBlendStyle("#ff0000", 1));
    let movingStyle = $state(defaultBlendStyle("#00ffff", 1));

    // Raw, because BlendRenderer uses private fields.
    let blendRenderer = $state.raw<BlendRenderer | null>(null);
    let stage: HTMLDivElement | undefined = $state();

    $effect(() => {
        const node = stage;
        const image = fixedImage;
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

    /**
     * The direct affine is a uniform, so point drags do not recompile.
     * Until that edge exists, any other baked path is shown instead.
     */
    const movingMapping = $derived.by((): BlendMapping => {
        const fixed = fixedImage;
        const moving = movingImage;
        const registration = viewerWindowContext.registration;
        void registration.revision;
        if (!fixed || !moving) return { affine: null };
        const affine = directAffineMatrix(
            registration.getRegistrationItem(fixed.image_id, moving.image_id),
        );
        if (affine) return { affine };
        return (
            glslPathBetween(
                registration,
                fixed.image_id,
                moving.image_id,
                (id) => registeredImageSize(viewerWindowContext, id),
            ) ?? { affine: null }
        );
    });

    $effect(() => {
        const renderer = blendRenderer;
        const fixed = fixedImage;
        const moving = movingImage;
        if (!renderer || !fixed) return;

        const layers: BlendLayer[] = [
            {
                image: fixed,
                mapping: fixedMapping,
                style: $state.snapshot(fixedStyle),
                weight: 1,
            },
        ];
        if (moving) {
            layers.push({
                image: moving,
                mapping: movingMapping,
                style: $state.snapshot(movingStyle),
                weight: 1,
            });
        }
        renderer.setLayers(layers);
        renderer.setComposite(composite, tile);
    });
</script>

<div class="blend">
    <div class="stage" bind:this={stage}></div>
    <aside class="controls">
        <fieldset class="composite">
            <legend>Blend</legend>
            <label>
                <input type="radio" bind:group={composite} value="overlay" />
                Colour overlay
            </label>
            <label>
                <input
                    type="radio"
                    bind:group={composite}
                    value="checkerboard"
                />
                Checkerboard
            </label>
            {#if composite === "checkerboard"}
                <label>
                    Tile
                    <input
                        type="range"
                        min="8"
                        max="512"
                        step="8"
                        bind:value={tile}
                        aria-label="Checkerboard tile size"
                        title="Tile size in pixels of the fixed image"
                    />
                </label>
            {/if}
        </fieldset>
        {#if fixedImage}
            <BlendLayerControls
                image={fixedImage}
                name="Fixed"
                bind:style={fixedStyle}
            />
        {/if}
        {#if movingImage}
            <BlendLayerControls
                image={movingImage}
                name="Moving"
                bind:style={movingStyle}
            />
        {/if}
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
    }

    .composite {
        display: flex;
        flex-direction: column;
        gap: 0.25em;
        margin: 0;
        padding: 0.4em;
        border: 1px solid rgba(255, 255, 255, 0.25);
    }

    .composite legend {
        font-size: 0.85em;
        padding: 0 0.25em;
    }

    label {
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
