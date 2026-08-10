<script lang="ts">
    import type { EnfaceProjectionMode } from "$lib/viewer/viewer-utils";

    interface Props {
        mode: EnfaceProjectionMode;
        size?: string;
        gradientId?: string;
    }

    let {
        mode,
        size = "2em",
        gradientId = "enface-projection-heatmap",
    }: Props = $props();
</script>

<svg
    xmlns="http://www.w3.org/2000/svg"
    class="icon"
    class:off={mode === "off"}
    class:binary={mode === "binary"}
    class:heatmap={mode === "heatmap"}
    width={size}
    height={size}
    viewBox="0 0 24 24"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
>
    {#if mode === "heatmap"}
        <defs>
            <linearGradient id={gradientId} x1="0%" y1="100%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#0000ff" />
                <stop offset="33%" stop-color="#00ff00" />
                <stop offset="66%" stop-color="#ffff00" />
                <stop offset="100%" stop-color="#ff0000" />
            </linearGradient>
        </defs>
    {/if}

    <path stroke="none" d="M0 0h24v24H0z" fill="none" />
    <polyline
        class="layer layer-top"
        points="12 4 4 8 12 12 20 8 12 4"
        fill="none"
        stroke="currentColor"
    />
    <polyline
        class="layer layer-mid"
        points="4 12 12 16 20 12"
        fill={mode === "binary" ? "currentColor" : "none"}
        stroke="currentColor"
    />
    <polyline
        class="layer layer-bottom"
        points="4 16 12 20 20 16"
        fill={mode === "heatmap" ? `url(#${gradientId})` : "none"}
        stroke="currentColor"
    />
</svg>

<style>
    svg {
        fill: none;
        stroke: currentColor;
        transition:
            opacity 0.2s ease,
            transform 0.2s ease;
    }

    svg.off {
        opacity: 0.45;
    }

    svg.binary .layer-mid,
    svg.heatmap .layer-bottom {
        stroke-width: 1.25;
    }

    svg.heatmap .layer-bottom {
        stroke: rgb(255 255 255 / 0.85);
    }
</style>
