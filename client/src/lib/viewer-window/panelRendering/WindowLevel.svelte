<script lang="ts">
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import WindowLevelSlider from "./WindowLevelSlider.svelte";

    const viewerContext = getContext<ViewerContext>("viewerContext");
</script>

<WindowLevelSlider bind:windowLevel={viewerContext.windowLevel} />
