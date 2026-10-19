<script lang="ts">
    import Viewer from "$lib/viewer/Viewer.svelte";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import {
        AffineBlendRenderer,
        parseHexColour,
    } from "$lib/webgl/affineBlendRenderer";
    import { getContext, mount, unmount, untrack } from "svelte";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import { directAffineMatrix } from "./directAffine";

    interface Props {
        images: AbstractImage[];
    }

    let { images }: Props = $props();

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );

    const fixedImage = $derived(images[0] ?? null);
    const movingImage = $derived(images[1] ?? null);

    let fixedMix = $state(1);
    let movingMix = $state(1);
    let fixedOpacity = $state(1);
    let movingOpacity = $state(1);
    let fixedColour = $state("#ff0000");
    let movingColour = $state("#00ffff");

    // AffineBlendRenderer uses private fields, so it stays a plain instance.
    // rendererEpoch is the signal that a new viewer context is ready.
    let blendRenderer: AffineBlendRenderer | null = null;
    let rendererEpoch = $state(0);

    let stage: HTMLDivElement | undefined = $state();

    // Viewer reads its context once. A new fixed image needs a new
    // ViewerContext, so the viewer is remounted rather than reused.
    $effect(() => {
        const node = stage;
        const image = fixedImage;
        if (!node || !image) return;

        const mounted = untrack(() => {
            const viewerContext = new ViewerContext(image, viewerWindowContext);
            const renderer = new AffineBlendRenderer(image.webgl);
            viewerContext.imageRenderer =
                renderer as unknown as typeof viewerContext.imageRenderer;
            const app = mount(Viewer, {
                target: node,
                props: { showInfo: false, foreground: true },
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
        const fixed = fixedImage;
        const moving = movingImage;
        const revision = viewerWindowContext.registration.revision;
        const nextFixedMix = fixedMix;
        const nextMovingMix = movingMix;
        const nextFixedOpacity = fixedOpacity;
        const nextMovingOpacity = movingOpacity;
        const nextFixedColour = fixedColour;
        const nextMovingColour = movingColour;
        void epoch;
        void revision;
        if (!renderer || !fixed) return;

        const affine = moving
            ? directAffineMatrix(
                  viewerWindowContext.registration.getRegistrationItem(
                      fixed.image_id,
                      moving.image_id,
                  ),
              )
            : null;
        renderer.setPair(fixed, affine && moving ? moving : null, affine);
        renderer.setTint(
            nextFixedMix,
            parseHexColour(nextFixedColour),
            nextFixedOpacity,
            nextMovingMix,
            parseHexColour(nextMovingColour),
            nextMovingOpacity,
        );
    });
</script>

<div class="blend">
    <div class="stage" bind:this={stage}></div>
    <aside class="controls">
        {#if fixedImage}
            {@render layer(
                "Fixed",
                fixedImage.instance.id,
                fixedMix,
                fixedColour,
                fixedOpacity,
                (value) => (fixedMix = value),
                (value) => (fixedColour = value),
                (value) => (fixedOpacity = value),
            )}
        {/if}
        {#if movingImage}
            {@render layer(
                "Moving",
                movingImage.instance.id,
                movingMix,
                movingColour,
                movingOpacity,
                (value) => (movingMix = value),
                (value) => (movingColour = value),
                (value) => (movingOpacity = value),
            )}
        {/if}
    </aside>
</div>

{#snippet layer(
    role: string,
    publicId: string,
    mix: number,
    colour: string,
    opacity: number,
    setMix: (value: number) => void,
    setColour: (value: string) => void,
    setOpacity: (value: number) => void,
)}
    <section class="layer">
        <div class="public-id" title={publicId}>{publicId}</div>
        <label>
            Colour
            <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={mix}
                aria-label="{role} tint"
                title="Left is the original colour, right is luminosity times the picked colour"
                oninput={(event) => setMix(Number(event.currentTarget.value))}
            />
            <input
                type="color"
                value={colour}
                aria-label="{role} colour"
                oninput={(event) => setColour(event.currentTarget.value)}
            />
        </label>
        <label>
            Opacity
            <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={opacity}
                aria-label="{role} opacity"
                oninput={(event) =>
                    setOpacity(Number(event.currentTarget.value))}
            />
        </label>
    </section>
{/snippet}

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

    input[type="color"] {
        flex: 0 0 auto;
        width: 2rem;
        height: 1.4rem;
        padding: 0;
        border: none;
        background: transparent;
        cursor: pointer;
    }
</style>
