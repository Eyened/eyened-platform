<script lang="ts">
    import { data } from "$lib/datamodel/model";
    import { loadInstances } from "$lib/utils/api";
    import type { Instance } from "$lib/datamodel/instance.svelte";
    import { Deferred } from "$lib/utils";
    import ImageWindow from "$lib/viewer-window/ImageWindow.svelte";
    import { WebGL } from "$lib/webgl/webgl";
    import { onMount } from "svelte";

    interface Props {
        data: { ImageInstanceID: number };
    }

    let { data: props_data }: Props = $props();
    const { ImageInstanceID } = props_data;

    let mainCanvas: HTMLCanvasElement;

    function resizeCanvas() {
        if (mainCanvas) {
            mainCanvas.width = window.innerWidth;
            mainCanvas.height = window.innerHeight;
        }
    }

    const { promise, resolve, reject } = new Deferred<{
        webgl: WebGL;
        instance: Instance;
    }>();

    onMount(async () => {
        if (!window) {
            return;
        }
        window.addEventListener("resize", resizeCanvas);

        resizeCanvas();

        const webgl = new WebGL(mainCanvas);

        await loadInstances([ImageInstanceID]);
        const instance = data.images.get(ImageInstanceID)!;
        if (!instance) {
            reject(new Error(`Instance with ID ${ImageInstanceID} not found`));
        }
        resolve({ webgl, instance });
    });
</script>

<svelte:head>
    <title>Image {ImageInstanceID}</title>
</svelte:head>

<canvas bind:this={mainCanvas} class="editor"></canvas>

{#await promise}
    Loading...
{:then { webgl, instance }}
    <ImageWindow {webgl} {instance} />
{:catch error}
    <div class="error">
        Something went wrong:
        <span>{error}</span>
    </div>
{/await}
