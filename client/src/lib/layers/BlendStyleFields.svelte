<!--
@component
One image's blend look, in the Blend section or a Series Style popover. Each field writes the window's style for this image and role, kept for the page session.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { Checkbox } from "$lib/components/ui/checkbox/index.js";
    import { Dropdown } from "$lib/components/ui/dropdown/index.js";
    import { Slider } from "$lib/components/ui/slider/index.js";
    import {
        getAvailableRenderModes,
        type RenderMode,
    } from "$lib/viewer/viewer-utils";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import type { BlendLayerStyle } from "$lib/webgl/blendRenderer";
    import type { BlendRole, BlendStyles } from "./blendStyles";

    type Field = "mode" | "wl" | "tint" | "colour" | "opacity" | "reset";

    let {
        image,
        role,
        styles,
        label,
        fields,
    }: {
        image: AbstractImage;
        role: BlendRole;
        styles: BlendStyles;
        label: string;
        fields: readonly Field[];
    } = $props();

    const uid = $props.id();
    const style = $derived(styles.get(image.image_id, role));
    const set = (change: Partial<BlendLayerStyle>) =>
        styles.set(image.image_id, role, change);
    // ASSUMPTION: our own set of saturated hues; no published source. It includes the three defaults: this image red, the other cyan, series white.
    const SWATCHES = [
        ["#ff0000", "Red"],
        ["#ff8000", "Orange"],
        ["#ffff00", "Yellow"],
        ["#00ff00", "Green"],
        ["#00ffff", "Cyan"],
        ["#0000ff", "Blue"],
        ["#ff00ff", "Magenta"],
        ["#ffffff", "White"],
    ] as const;
    const selectedSwatch = $derived(
        SWATCHES.some(([hex]) => hex === style.colour),
    );

    function swatchKeys(e: KeyboardEvent & { currentTarget: HTMLElement }) {
        const step = {
            ArrowRight: 1,
            ArrowDown: 1,
            ArrowLeft: -1,
            ArrowUp: -1,
        }[e.key];
        if (step === undefined) return;
        e.preventDefault();
        const i = SWATCHES.findIndex(([hex]) => hex === style.colour);
        const next =
            (Math.max(i, 0) + step + SWATCHES.length) % SWATCHES.length;
        set({ colour: SWATCHES[next][0] });
        (e.currentTarget.children[next] as HTMLElement).focus();
    }
    const modes = $derived(
        getAvailableRenderModes(image.supportsColorRenderModes).map((mode) => ({
            id: mode,
            text: mode,
        })),
    );
</script>

<div role="group" aria-labelledby="{uid}-name" class="flex flex-col gap-2">
    <p id="{uid}-name" class="text-label-01 text-text-secondary">{label}</p>
    {#if fields.includes("mode")}
        <Dropdown
            size="md"
            labelText="Render mode"
            items={modes}
            selectedId={style.renderMode}
            onselect={(mode) => set({ renderMode: mode as RenderMode })}
        />
    {/if}
    {#if fields.includes("wl")}
        <div class="flex items-center gap-2">
            <span class="text-label-01 text-text-secondary">W/L</span>
            <Slider
                class="flex-1"
                min={0}
                max={255}
                labels={["Window low", "Window high"]}
                valueTexts={[
                    String(Math.round(style.windowLevel.min)),
                    String(Math.round(style.windowLevel.max)),
                ]}
                tooltip
                values={[
                    Math.round(style.windowLevel.min),
                    Math.round(style.windowLevel.max),
                ]}
                onchange={([min, max]) => set({ windowLevel: { min, max } })}
            />
        </div>
    {/if}
    {#if fields.includes("tint")}
        <div class="flex items-center gap-2">
            <span class="text-label-01 text-text-secondary">Tint</span>
            <Slider
                class="flex-1"
                min={0}
                max={100}
                labels={["Tint"]}
                valueTexts={[`${Math.round(style.tint * 100)}%`]}
                tooltip
                values={[Math.round(style.tint * 100)]}
                onchange={([tint]) => set({ tint: tint / 100 })}
            />
        </div>
    {/if}
    {#if fields.includes("colour")}
        <div class="flex flex-col gap-1">
            <span id="{uid}-colour" class="text-label-01 text-text-secondary"
                >Tint colour</span
            >
            <!-- S2 ColorSwatchPicker: one Tab stop, arrow keys move and select. -->
            <div
                role="radiogroup"
                aria-labelledby="{uid}-colour"
                tabindex="-1"
                class="flex flex-wrap gap-1"
                onkeydown={swatchKeys}
            >
                {#each SWATCHES as [hex, name] (hex)}
                    {@const on = style.colour === hex}
                    <button
                        type="button"
                        role="radio"
                        aria-checked={on}
                        aria-label={name}
                        title={name}
                        tabindex={on ||
                        (!selectedSwatch && hex === SWATCHES[0][0])
                            ? 0
                            : -1}
                        class="size-6 border border-border-strong-01 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus aria-checked:outline-2 aria-checked:outline-offset-2 aria-checked:outline-text-primary"
                        style:background-color={hex}
                        onclick={() => set({ colour: hex })}
                    ></button>
                {/each}
            </div>
        </div>
    {/if}
    {#if fields.includes("opacity")}
        <div class="flex items-center gap-2">
            <span class="text-label-01 text-text-secondary">Opacity</span>
            <Slider
                class="flex-1"
                min={0}
                max={100}
                labels={["Opacity"]}
                valueTexts={[`${Math.round(style.opacity * 100)}%`]}
                tooltip
                values={[Math.round(style.opacity * 100)]}
                onchange={([opacity]) => set({ opacity: opacity / 100 })}
            />
        </div>
    {/if}
    <div class="flex items-center gap-2">
        <Checkbox
            id="{uid}-invert"
            checked={style.invert}
            onCheckedChange={(on) => set({ invert: on === true })}
        />
        <label for="{uid}-invert" class="text-body-compact-01 text-text-primary"
            >Invert</label
        >
    </div>
    {#if fields.includes("reset")}
        <Button
            variant="ghost"
            size="sm"
            class="self-start"
            onclick={() => styles.reset(image.image_id, role)}>Reset</Button
        >
    {/if}
</div>
