<script lang="ts">
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { getContext, onDestroy, onMount } from "svelte";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import SeriesBlend from "./SeriesBlend.svelte";
    import SeriesImage from "./SeriesImage.svelte";

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );

    const session = $derived(viewerWindowContext.seriesBlend);

    function resolveImages(
        imageIds: readonly string[],
    ): AbstractImage[] | null {
        const images: AbstractImage[] = [];
        for (const id of imageIds) {
            let match: AbstractImage | undefined;
            for (const image of viewerWindowContext.topViewers.keys()) {
                if (image.image_id === id) {
                    match = image;
                    break;
                }
            }
            if (!match) return null;
            images.push(match);
        }
        return images;
    }

    const images = $derived(session ? resolveImages(session.imageIds) : null);

    // A missing id would leave background viewers paused, so close instead.
    $effect.pre(() => {
        const current = viewerWindowContext.seriesBlend;
        if (!current) return;
        if (!resolveImages(current.imageIds)) {
            viewerWindowContext.closeSeriesBlend();
        }
    });

    let root: HTMLDivElement | undefined = $state();
    let isResizing = false;

    function startResize(event: PointerEvent) {
        isResizing = true;
        event.preventDefault();
    }

    function stopResize() {
        isResizing = false;
    }

    function doResize(event: PointerEvent) {
        if (!isResizing || !root) return;
        root.style.setProperty(
            "grid-template-rows",
            `${event.clientY}px 1px 1fr`,
        );
    }

    onMount(() => {
        root?.focus();
        window.addEventListener("pointerup", stopResize);
        window.addEventListener("pointermove", doResize);
    });

    onDestroy(() => {
        window.removeEventListener("pointerup", stopResize);
        window.removeEventListener("pointermove", doResize);
    });
</script>

{#if session && images}
    <svelte:boundary onerror={() => viewerWindowContext.closeSeriesBlend()}>
        <div
            class="editor"
            bind:this={root}
            role="dialog"
            aria-modal="true"
            aria-label="Series blend"
            tabindex="-1"
        >
            <button
                type="button"
                class="close"
                onclick={() => viewerWindowContext.closeSeriesBlend()}
            >
                Close
            </button>
            <div class="thumbs">
                {#each images as image (image.image_id)}
                    <SeriesImage {image} />
                {/each}
            </div>
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div class="resizer" onpointerdown={startResize}>
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <div class="handle" onpointerdown={startResize}><hr /></div>
            </div>
            <SeriesBlend {images} />
        </div>
    </svelte:boundary>
{/if}

<style>
    .editor {
        position: fixed;
        inset: 0;
        z-index: 200;
        /* The window canvas is cleared black and sits under this layer.
           An opaque background here would cover the blended images. */
        background: transparent;
        display: grid;
        grid-template-rows: 34% 1px 1fr;
        outline: none;
    }

    .close {
        position: absolute;
        top: 0.4em;
        right: 0.4em;
        z-index: 2;
        background-color: rgba(0, 0, 0, 0.92);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 0.25em;
        padding: 0.35em 0.65em;
        cursor: pointer;
    }

    .thumbs {
        min-height: 0;
        display: flex;
        overflow: hidden;
    }

    .resizer {
        position: relative;
        background-color: gray;
    }

    .handle {
        position: absolute;
        top: -3px;
        left: 50%;
        transform: translateX(-50%);
        width: 30px;
        height: 6px;
        background: #ccc;
        border-radius: 2px;
        border: 1px solid rgba(0, 0, 0, 0.3);
        cursor: row-resize;
        z-index: 2;
    }

    .handle hr {
        margin: 2px;
        border-top: 1px solid rgba(0, 0, 0, 0.4);
        background-color: rgba(255, 255, 255, 0.9);
    }
</style>
