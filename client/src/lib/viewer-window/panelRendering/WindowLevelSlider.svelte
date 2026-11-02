<script lang="ts">
    import type { WindowLevel } from "$lib/viewer/viewer-utils";
    import DoubleRangeSlider from "../DoubleRangeSlider.svelte";
    import Brightness from "../icons/Brightness.svelte";

    interface Props {
        /** 0–255 */
        windowLevel: WindowLevel;
        iconSize?: string;
        /** Stretch to the container instead of a fixed 10em slider. */
        fill?: boolean;
    }

    let {
        windowLevel = $bindable(),
        iconSize = "2em",
        fill = false,
    }: Props = $props();

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

<div class="container" class:fill>
    <Brightness size={iconSize} />
    <div class="slider">
        <DoubleRangeSlider bind:start={w.start} bind:end={w.end} />
    </div>
</div>

<style>
    div.container {
        display: flex;
    }
    div.slider {
        margin: 0em 1em;
        width: 10em;
    }
    div.fill {
        align-items: center;
    }
    div.fill div.slider {
        flex: 1;
        width: auto;
        min-width: 0;
    }
</style>
