<script lang="ts">
    import Viewer from "$lib/viewer/Viewer.svelte";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { getContext, setContext, untrack } from "svelte";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";

    interface Props {
        image: AbstractImage;
    }

    let { image }: Props = $props();

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );
    const viewerContext = new ViewerContext(
        untrack(() => image),
        viewerWindowContext,
    );
    setContext("viewerContext", viewerContext);
</script>

<div class="thumb">
    <Viewer showInfo={false} />
</div>

<style>
    .thumb {
        flex: 1;
        min-width: 0;
        display: flex;
        position: relative;
    }
</style>
