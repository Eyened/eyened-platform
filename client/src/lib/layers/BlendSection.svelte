<!--
@component
Layers › Blend for the selected viewport: how this viewport draws its image with another. Pair modes use the eye's current registration; Series uses every registered image of the eye.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { RadioButton } from "$lib/components/ui/radio-button/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { Slider } from "$lib/components/ui/slider/index.js";
    import { ToggleGroup } from "$lib/components/ui/toggle-group/index.js";
    import { getThumbUrl } from "$lib/data-loading/utils";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import BlendStyleFields from "./BlendStyleFields.svelte";
    import SeriesBody from "./SeriesBody.svelte";
    import LayerSection from "./LayerSection.svelte";
    import type { BlendMode, ViewportBlend } from "./viewportBlend.svelte";

    let {
        blend,
        open,
        ontoggle,
    }: { blend: ViewportBlend; open: boolean; ontoggle: () => void } = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { image } = viewerContext;
    const styles = viewerContext.viewerWindowContext.blendStyles;
    const uid = $props.id();

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
    const withRows = $derived(
        blend.candidates.map((candidate) => {
            const n = blend.pairs(candidate);
            return {
                id: candidate.image_id,
                ...blend.nameOf(candidate),
                pairs: `${n} pair${n === 1 ? "" : "s"}`,
                thumb: getThumbUrl(candidate.instance),
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
            class="max-w-full self-start"
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
                <fieldset class="flex min-w-0 flex-col">
                    <legend class="mb-2 text-label-01 text-text-secondary">
                        With · Registration [{blend.registration.id}]
                    </legend>
                    {#each withRows as row, i (row.id)}
                        <!-- Two images can share the name line and differ only by device, so both lines name the radio. -->
                        <RadioButton
                            name="{uid}-with"
                            value={row.id}
                            checked={row.id === blend.other.image_id}
                            onchange={() => blend.setWith(row.id)}
                            labelledBy={row.device
                                ? `${uid}-name-${i} ${uid}-device-${i}`
                                : `${uid}-name-${i}`}
                            describedBy="{uid}-pairs-{i}"
                            class="flex py-1"
                        >
                            <span class="flex items-start gap-2">
                                <img
                                    src={row.thumb}
                                    alt=""
                                    class="size-6 shrink-0 object-cover"
                                />
                                <span
                                    class="min-w-0 flex-1 [overflow-wrap:anywhere]"
                                >
                                    <span id="{uid}-name-{i}" class="block"
                                        >{row.name}</span
                                    >
                                    {#if row.device}
                                        <span
                                            id="{uid}-device-{i}"
                                            class="block text-label-01 text-text-secondary"
                                            >{row.device}</span
                                        >
                                    {/if}
                                </span>
                                <span
                                    id="{uid}-pairs-{i}"
                                    class="shrink-0 text-label-01 text-text-secondary tabular-nums"
                                    >{row.pairs}</span
                                >
                            </span>
                        </RadioButton>
                    {/each}
                </fieldset>
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
                    label={blend.nameOf(blend.other).name}
                    fields={tinted
                        ? ["mode", "wl", "tint", "colour", "opacity", "reset"]
                        : ["mode", "wl", "reset"]}
                />
            {/if}
        {/if}
    </div>
</LayerSection>
