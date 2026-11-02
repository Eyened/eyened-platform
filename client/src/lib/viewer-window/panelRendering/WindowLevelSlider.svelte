<script lang="ts">
    import type { WindowLevel } from "$lib/viewer/viewer-utils";
    import DoubleRangeSlider from "../DoubleRangeSlider.svelte";
    import Brightness from "../icons/Brightness.svelte";

    interface Props {
        /** 0–255 */
        windowLevel: WindowLevel;
        iconSize?: string;
    }

    let { windowLevel = $bindable(), iconSize = "2em" }: Props = $props();

    const w = {
        get start() {
            return windowLevel.min / 255;
        },
        set start(value) {
            windowLevel.min = value * 255;
        },
        get end() {
            return windowLevel.max / 255;
        },
        set end(value) {
            windowLevel.max = value * 255;
        },
    };
</script>

<div class="container">
    <Brightness size={iconSize} />
    <div class="slider">
        <DoubleRangeSlider bind:start={w.start} bind:end={w.end} />
    </div>
</div>

<style>
    div.container {
        display: flex;
        align-items: center;
    }
    div.slider {
        flex: 1;
        margin: 0em 1em;
        min-width: 6em;
        max-width: 10em;
    }
</style>
