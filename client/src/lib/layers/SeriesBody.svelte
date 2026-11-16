<!--
@component
Blend › Series: the eye's registered images oldest first, a Position slider that walks the ticked ones, and a Style popover per image.
-->
<script lang="ts">
    import { Checkbox } from "$lib/components/ui/checkbox/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import { Slider } from "$lib/components/ui/slider/index.js";
    import { getThumbUrl } from "$lib/data-loading/utils";
    import { MODALITY_LABELS } from "$lib/workspace/imageMeta";
    import ChevronLeft from "carbon-icons-svelte/lib/ChevronLeft.svelte";
    import ChevronRight from "carbon-icons-svelte/lib/ChevronRight.svelte";
    import Settings from "carbon-icons-svelte/lib/Settings.svelte";
    import type { ImageGET } from "../../types/openapi_types";
    import BlendStyleFields from "./BlendStyleFields.svelte";
    import type { BlendStyles } from "./blendStyles";
    import { shortImageLabel } from "./pointsets";
    import type { ViewportBlend } from "./viewportBlend.svelte";

    let {
        blend,
        styles,
        thisId,
    }: { blend: ViewportBlend; styles: BlendStyles; thisId: string } = $props();

    const uid = $props.id();
    const others = $derived(blend.seriesItems.length - 1);
    const ticked = $derived(new Set(blend.ticked));
    const full = $derived(ticked.size >= blend.cap);
    const walkable = $derived(blend.shown.length > 1);
    const showingId = $derived(walkable ? blend.showing?.image_id : undefined);

    /** "CF · Topcon". */
    function description(instance: ImageGET): string {
        const modality = instance.modality
            ? (MODALITY_LABELS[instance.modality] ?? instance.modality)
            : "";
        return [modality, instance.device.manufacturer]
            .filter(Boolean)
            .join(" · ");
    }

    // Page Up / Down on the slider jump between images; caught before the handle's own keys.
    function pageKeys(e: KeyboardEvent) {
        if (e.key !== "PageUp" && e.key !== "PageDown") return;
        e.preventDefault();
        e.stopPropagation();
        blend.step(e.key === "PageUp" ? 1 : -1);
    }
</script>

{#if others === 0}
    <p class="text-body-compact-01 text-text-secondary">
        No other loaded image of this eye is registered to this one.
    </p>
{:else}
    <p class="text-body-compact-01 text-text-primary">
        Series · {others} registered image{others === 1 ? "" : "s"}
    </p>
    <div class="flex items-center gap-1" onkeydowncapture={pageKeys}>
        <IconButton
            size="icon-xs"
            label="Previous image"
            disabled={!walkable}
            onclick={() => blend.step(-1)}><ChevronLeft /></IconButton
        >
        <Slider
            class="mx-2 flex-1"
            disabled={!walkable}
            min={0}
            max={Math.max(blend.shown.length - 1, 1)}
            step={0.01}
            labels={["Position"]}
            valueTexts={[blend.showing?.instance.study.date ?? ""]}
            tooltip
            values={[blend.seriesPosition]}
            onchange={([position]) => blend.setPosition(position)}
            ondoubleclick={() => blend.setPosition(null)}
        />
        <IconButton
            size="icon-xs"
            label="Next image"
            disabled={!walkable}
            onclick={() => blend.step(1)}><ChevronRight /></IconButton
        >
    </div>
    {#if !walkable}
        <p class="text-helper-text-01 text-text-helper">
            Tick another image to walk a series.
        </p>
    {/if}
    {#if full}
        <p class="text-helper-text-01 text-text-helper">
            At most {blend.cap} images at once on this device
        </p>
    {/if}
    <ul>
        {#each blend.seriesItems as { image } (image.image_id)}
            {@const isThis = image.image_id === thisId}
            {@const on = ticked.has(image.image_id)}
            {@const label = shortImageLabel(image.instance)}
            <li
                class="flex items-start gap-2 border-s-3 py-1 ps-2 {image.image_id ===
                showingId
                    ? 'border-border-interactive'
                    : 'border-transparent'}"
            >
                <Checkbox
                    id="{uid}-{image.image_id}"
                    class="mt-1"
                    checked={on}
                    disabled={isThis || (!on && full)}
                    onCheckedChange={() => blend.toggleTick(image.image_id)}
                />
                <!-- The image's Series tint at a glance; changed in its Style popover. -->
                <span
                    aria-hidden="true"
                    class="mt-1.5 size-3 shrink-0 border border-border-strong-01"
                    style:background-color={styles.get(image.image_id, "series")
                        .colour}
                ></span>
                <img
                    src={getThumbUrl(image.instance)}
                    alt=""
                    class="size-6 shrink-0 object-cover"
                />
                <label for="{uid}-{image.image_id}" class="min-w-0 flex-1">
                    <span
                        class="block text-body-compact-01 [overflow-wrap:anywhere] text-text-primary"
                        >{image.instance.study.date}{isThis
                            ? " · this image"
                            : ""}</span
                    >
                    <span class="block text-helper-text-01 text-text-secondary"
                        >{description(image.instance)}{image.image_id ===
                        showingId
                            ? " · showing"
                            : ""}</span
                    >
                </label>
                <Popover.Root>
                    <Popover.Trigger>
                        {#snippet child({ props })}
                            <IconButton
                                {...props}
                                size="icon-xs"
                                label="Style, {label}"><Settings /></IconButton
                            >
                        {/snippet}
                    </Popover.Trigger>
                    <Popover.Content
                        data-slot="filter-popover"
                        role="dialog"
                        aria-label="Style, {label}"
                        side="left"
                        align="start"
                        class="flex w-60 flex-col gap-3 shadow-popover"
                    >
                        <BlendStyleFields
                            {image}
                            role="series"
                            {styles}
                            {label}
                            fields={isThis
                                ? ["tint", "opacity"]
                                : [
                                      "mode",
                                      "wl",
                                      "tint",
                                      "colour",
                                      "opacity",
                                      "reset",
                                  ]}
                        />
                    </Popover.Content>
                </Popover.Root>
            </li>
        {/each}
    </ul>
{/if}
