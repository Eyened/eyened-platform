<script lang="ts">
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import type { BlendLayerStyle } from "$lib/webgl/blendRenderer";
    import RenderModeSelect from "../panelRendering/RenderModeSelect.svelte";
    import WindowLevelSlider from "../panelRendering/WindowLevelSlider.svelte";

    interface Props {
        image: AbstractImage;
        /** Prefix for control labels, e.g. "Fixed" or a public id. */
        name: string;
        style: BlendLayerStyle;
    }

    let { image, name, style = $bindable() }: Props = $props();
</script>

<section class="layer">
    <div class="public-id" title={image.instance.id}>{image.instance.id}</div>
    <RenderModeSelect
        bind:value={style.renderMode}
        supportsColor={image.supportsColorRenderModes}
        label="{name} render mode"
    />
    <WindowLevelSlider bind:windowLevel={style.windowLevel} iconSize="1.4em" />
    <label>
        Colour
        <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={style.tint}
            aria-label="{name} tint"
            title="Left is the original colour, right is luminosity times the picked colour"
            oninput={(event) =>
                (style.tint = Number(event.currentTarget.value))}
        />
        <input
            type="color"
            value={style.colour}
            aria-label="{name} colour"
            oninput={(event) => (style.colour = event.currentTarget.value)}
        />
    </label>
    <label>
        Opacity
        <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={style.opacity}
            aria-label="{name} opacity"
            oninput={(event) =>
                (style.opacity = Number(event.currentTarget.value))}
        />
    </label>
</section>

<style>
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
