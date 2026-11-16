<!--
@component
Layers › Blend for the selected viewport: how this viewport draws its image with another. Pair modes use the eye's current registration; Series uses every registered image of the eye.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { Dropdown } from "$lib/components/ui/dropdown/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { Slider } from "$lib/components/ui/slider/index.js";
    import { ToggleGroup } from "$lib/components/ui/toggle-group/index.js";
    import { getThumbUrl } from "$lib/data-loading/utils";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import BlendStyleFields from "./BlendStyleFields.svelte";
    import SeriesBody from "./SeriesBody.svelte";
    import LayerSection from "./LayerSection.svelte";
    import { shortImageLabel } from "./pointsets";
    import type { BlendMode, ViewportBlend } from "./viewportBlend.svelte";

    let {
        blend,
        open,
        ontoggle,
    }: { blend: ViewportBlend; open: boolean; ontoggle: () => void } = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { image } = viewerContext;
    const styles = viewerContext.viewerWindowContext.blendStyles;

    const MODES = [
        { value: "off", text: "Off", label: "Off" },
        {
            value: "overlay",
            text: "Overlay",
            label: "Colour overlay",
            tooltip: "Colour overlay",
        },
        {
            value: "checker",
            text: "Checker",
            label: "Checkerboard",
            tooltip: "Checkerboard",
        },
        { value: "flicker", text: "Flicker", label: "Flicker" },
        { value: "series", text: "Series", label: "Series" },
    ];

    // Flicker shows each image whole, so only Overlay and Checker tint.
    const tinted = $derived(
        blend.mode === "overlay" || blend.mode === "checker",
    );
    const withItems = $derived(
        blend.candidates.map((candidate) => {
            const n = blend.pairs(candidate);
            return {
                id: candidate.image_id,
                text: shortImageLabel(candidate.instance),
                description: `${n} pair${n === 1 ? "" : "s"}`,
                thumb: getThumbUrl(candidate.instance, 48),
            };
        }),
    );
</script>

<LayerSection title="Blend" {open} {ontoggle}>
    <div class="flex flex-col gap-3 px-4 py-2">
        <ToggleGroup
            label="Blend"
            value={blend.mode}
            onchange={(mode) => blend.setMode(mode as BlendMode)}
            items={MODES}
            class="self-start"
        />
        {#if blend.error}
            <InlineNotification
                title="Couldn't blend these images"
                role="status"
            />
        {/if}
        {#if blend.mode === "series"}
            <SeriesBody {blend} {styles} thisId={image.image_id} />
        {/if}
        {#if blend.mode !== "off" && blend.mode !== "series"}
            {#if !blend.registration}
                <p class="text-body-compact-01 text-text-secondary">
                    Make a registration current in Pointsets.
                </p>
            {:else if !blend.other}
                <!-- ASSUMPTION: the spec gives no text for a registration without another loaded image. -->
                <p class="text-body-compact-01 text-text-secondary">
                    No other loaded image is in Registration [{blend
                        .registration.id}].
                </p>
            {:else}
                <p class="text-label-01 text-text-secondary" aria-hidden="true">
                    With · Registration [{blend.registration.id}]
                </p>
                <Dropdown
                    labelText="With"
                    hideLabel
                    size="md"
                    items={withItems}
                    selectedId={blend.other.image_id}
                    onselect={(id) => blend.setWith(id)}
                />
                {#if blend.mode === "checker"}
                    <div class="flex items-center gap-2">
                        <span class="text-label-01 text-text-secondary"
                            >Tile size</span
                        >
                        <Slider
                            class="flex-1"
                            min={8}
                            max={512}
                            step={8}
                            labels={["Tile size"]}
                            valueTexts={[`${blend.tile} px`]}
                            tooltip
                            values={[blend.tile]}
                            onchange={([tile]) => (blend.tile = tile)}
                        />
                    </div>
                {/if}
                {#if blend.mode === "flicker"}
                    <div class="flex gap-2">
                        <Button
                            variant="ghost"
                            size="sm"
                            disabled={!blend.aligned}
                            onclick={() =>
                                blend.playing ? blend.pause() : blend.play()}
                            >{blend.playing
                                ? "Pause flicker"
                                : "Play flicker"}</Button
                        >
                        <Button
                            variant="ghost"
                            size="sm"
                            disabled={blend.playing || !blend.aligned}
                            onclick={() => blend.swap()}>Swap</Button
                        >
                    </div>
                {/if}
                <BlendStyleFields
                    {image}
                    role="this"
                    {styles}
                    label="This image"
                    fields={tinted ? ["tint", "opacity"] : []}
                />
                <BlendStyleFields
                    image={blend.other}
                    role="other"
                    {styles}
                    label={shortImageLabel(blend.other.instance)}
                    fields={tinted
                        ? ["mode", "wl", "tint", "colour", "opacity", "reset"]
                        : ["mode", "wl", "reset"]}
                />
            {/if}
        {/if}
    </div>
</LayerSection>
