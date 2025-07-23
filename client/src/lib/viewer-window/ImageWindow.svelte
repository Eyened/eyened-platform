<script lang="ts">
    import { getContext } from "svelte";
    import { ImageLoader } from "$lib/data-loading/imageLoader";
    import type { Instance } from "$lib/datamodel/instance.svelte";
    import type { WebGL } from "$lib/webgl/webgl";
    import { setContext } from "svelte";
    import BaseViewer from "./BaseViewer.svelte";
    import { ViewerWindowContext } from "./viewerWindowContext.svelte";
    import { Registration } from "$lib/registration/registration";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";

    interface Props {
        instance: Instance;
        webgl: WebGL;
    }

    let { instance, webgl }: Props = $props();

    const imageLoader = new ImageLoader(webgl);
    const globalContext = getContext<GlobalContext>("globalContext");
    const { creator } = globalContext;
    const registration = new Registration();
    const viewerWindowContext = new ViewerWindowContext(
        webgl,
        registration,
        creator,
        [instance.id],
    );
    setContext("viewerWindowContext", viewerWindowContext);

    const loading = imageLoader.load(instance);
</script>

<div id="main">
    {#await loading}
        <div class="itemLoading">Loading {instance.id}</div>
    {:then images}
        {#each images as image}
            <div class="item">
                <BaseViewer {image} />
            </div>
        {/each}
    {/await}
</div>

<style>
    :global(body) {
        margin: 0;
        height: 100vh;
        font-family: Verdana, sans-serif;
        background-color: white;
    }
    :global(canvas) {
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        right: 0;
    }
    div {
        flex: 1;
        display: flex;
    }

    div.itemLoading {
        flex: 1;
        color: white;
    }

    div#main {
        position: fixed;
        top: 0;
        left: 0;
        bottom: 0;
        right: 0;
        display: flex;
        flex-direction: column;
    }
</style>
