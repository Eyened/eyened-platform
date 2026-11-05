<!--
@component
The Layout button and its popover: the preset grid and the Arrange orders, each one tab stop.
Arrow keys move focus only; Enter, Space or a click applies.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import ChevronDown from "carbon-icons-svelte/lib/ChevronDown.svelte";
    import { Checkbox } from "$lib/components/ui/checkbox/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
    import { getContext, tick, untrack } from "svelte";
    import { PRESET_ROWS, smallestRowFor } from "./presets";
    import { rovingIndex } from "./rovingIndex";
    import type { Workspace } from "./workspace.svelte";
    import { ARRANGE_ORDERS, type ArrangeOrder } from "./workspaceRules";
    import { writeStripOn } from "./workspacePrefs";

    let {
        stripToggle = false,
        anchor,
        open = $bindable(false),
    }: {
        stripToggle?: boolean;
        /** CSS selector of an outside element to hang from; no trigger is rendered. */
        anchor?: string;
        open?: boolean;
    } = $props();

    const workspace = getContext<Workspace>("workspace");
    const uid = $props.id();
    const ARRANGE_LABELS: Record<ArrangeOrder, string> = {
        opened: "Opened order",
        visit: "By visit",
        eye: "By eye",
        modality: "By modality",
    };
    const flat = PRESET_ROWS.flatMap((row, r) =>
        row.presets.map((preset, c) => ({ preset, r, c })),
    );

    let content: HTMLElement | null = $state(null);
    let triggerWrap: HTMLElement | undefined = $state();
    let presetFocus = $state(0);
    let arrangeFocus = $state(0);
    const openCount = $derived(workspace.catalogue.length);
    const fitRow = $derived(smallestRowFor(openCount).count);

    const frs = (sizes: readonly number[]) =>
        sizes.map((s) => `${s}fr`).join(" ");
    const indexOf = (r: number, c: number) =>
        flat.findIndex((f) => f.r === r && f.c === c);

    // Opening, from the trigger or from outside, starts both tab stops on the current choice.
    $effect.pre(() => {
        if (!open) return;
        untrack(() => {
            presetFocus = Math.max(
                0,
                flat.findIndex((f) => f.preset.id === workspace.preset.id),
            );
            arrangeFocus = Math.max(
                0,
                ARRANGE_ORDERS.indexOf(workspace.arrange),
            );
        });
    });

    /** Without a trigger, closing returns focus to the outside anchor. */
    function onCloseAutoFocus(e: Event) {
        if (!anchor) return;
        e.preventDefault();
        document.querySelector<HTMLElement>(anchor)?.focus();
    }

    async function focusItem(selector: string) {
        await tick();
        content?.querySelector<HTMLElement>(selector)?.focus();
    }

    function presetKey(e: KeyboardEvent, i: number) {
        const { r, c } = flat[i];
        let next: number;
        if (e.key === "ArrowRight") next = Math.min(i + 1, flat.length - 1);
        else if (e.key === "ArrowLeft") next = Math.max(i - 1, 0);
        else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            const row = r + (e.key === "ArrowDown" ? 1 : -1);
            if (row < 0 || row >= PRESET_ROWS.length) return;
            next = indexOf(
                row,
                Math.min(c, PRESET_ROWS[row].presets.length - 1),
            );
        } else if (e.key === "Home") next = 0;
        else if (e.key === "End") next = flat.length - 1;
        else return;
        e.preventDefault();
        presetFocus = next;
        void focusItem(`[data-preset-index="${next}"]`);
    }

    function arrangeKey(e: KeyboardEvent, i: number) {
        const next = rovingIndex(e.key, i, ARRANGE_ORDERS.length, {
            prev: ["ArrowUp", "ArrowLeft"],
            next: ["ArrowDown", "ArrowRight"],
        });
        if (next === null) return;
        e.preventDefault();
        arrangeFocus = next;
        void focusItem(`[data-arrange-index="${next}"]`);
    }

    function setStrip(on: boolean) {
        workspace.strip = on;
        writeStripOn(on);
    }

    // Carbon Popover: Tab out of the last control closes it.
    function onfocusout(e: FocusEvent) {
        const to = e.relatedTarget as Node | null;
        if (!to || content?.contains(to) || triggerWrap?.contains(to)) return;
        open = false;
    }
</script>

<Popover.Root bind:open>
    {#if !anchor}
        <span bind:this={triggerWrap} class="contents">
            <Popover.Trigger>
                {#snippet child({ props })}
                    <Button {...props} variant="ghost" size="sm"
                        >Layout <ChevronDown /></Button
                    >
                {/snippet}
            </Popover.Trigger>
        </span>
    {/if}
    <!-- ASSUMPTION: below md the popover hangs from ☰ at the left edge, so it aligns to its start. -->
    <Popover.Content
        bind:ref={content}
        align={anchor ? "start" : "end"}
        customAnchor={anchor && open
            ? document.querySelector<HTMLElement>(anchor)
            : null}
        {onCloseAutoFocus}
        trapFocus={false}
        portalProps={{ disabled: true }}
        class="max-h-[calc(100dvh-4rem)] overflow-y-auto"
        {onfocusout}
    >
        <h2 id="{uid}-layout" class="mb-1 text-label-01 text-text-secondary">
            Layout
        </h2>
        <!-- ASSUMPTION: aria-pressed buttons with a roving tab stop; bits-ui RadioGroup selects on focus (plan decision 1). -->
        <div role="group" aria-labelledby="{uid}-layout" class="flex flex-col">
            {#each PRESET_ROWS as row, r (row.count)}
                <div
                    role="group"
                    aria-label="{row.count} viewports"
                    class={[
                        "flex min-h-7 items-center gap-1 px-1",
                        fitRow === row.count && "bg-layer-selected-01",
                    ]}
                >
                    <span
                        class="w-5 text-end text-label-01 text-text-secondary"
                        aria-hidden="true"
                    >
                        {row.count}
                    </span>
                    {#each row.presets as preset, c (preset.id)}
                        {@const i = indexOf(r, c)}
                        <button
                            type="button"
                            class="preset"
                            data-preset-index={i}
                            aria-label={preset.label}
                            aria-pressed={workspace.preset.id === preset.id}
                            tabindex={i === presetFocus ? 0 : -1}
                            onclick={() => workspace.setPreset(preset.id)}
                            onkeydown={(e) => presetKey(e, i)}
                        >
                            <span
                                class="preview"
                                style="grid-template-columns: {frs(
                                    preset.cols,
                                )}; grid-template-rows: {frs(preset.rows)};"
                                aria-hidden="true"
                            >
                                {#each preset.cells as cell, k (k)}
                                    <i
                                        style="grid-column: {cell.col +
                                            1} / span {cell.colSpan}; grid-row: {cell.row +
                                            1};"
                                    ></i>
                                {/each}
                            </span>
                        </button>
                    {/each}
                    {#if fitRow === row.count && openCount <= row.count}
                        <span class="sr-only"
                            >Fits {openCount} open {openCount === 1
                                ? "image"
                                : "images"}</span
                        >
                    {/if}
                    {#if row.count === 16 && openCount > 16}
                        <span class="ms-auto text-label-01 text-text-secondary">
                            {openCount} open: {Math.ceil(openCount / 16)} pages
                        </span>
                    {/if}
                </div>
            {/each}
        </div>
        <h2
            id="{uid}-arrange"
            class="mt-3 mb-1 text-label-01 text-text-secondary"
        >
            Arrange
        </h2>
        <div role="group" aria-labelledby="{uid}-arrange" class="flex flex-col">
            {#each ARRANGE_ORDERS as order, i (order)}
                <button
                    type="button"
                    class="flex h-8 items-center px-2 text-body-compact-01 text-text-primary hover:bg-layer-hover-01 aria-pressed:bg-layer-selected-01"
                    data-arrange-index={i}
                    aria-pressed={workspace.arrange === order}
                    tabindex={i === arrangeFocus ? 0 : -1}
                    onclick={() => workspace.setArrange(order)}
                    onkeydown={(e) => arrangeKey(e, i)}
                >
                    {ARRANGE_LABELS[order]}
                </button>
            {/each}
        </div>
        {#if stripToggle}
            <!-- ASSUMPTION: a checkbox is the toggle (plan decision 19); a task sets the strip in its config. -->
            <Field.Field orientation="horizontal" class="mt-3 px-2">
                <Checkbox
                    id="{uid}-strip"
                    bind:checked={() => workspace.strip, setStrip}
                />
                <Field.Label
                    for="{uid}-strip"
                    class="text-body-compact-01 text-text-primary"
                >
                    Thumbnail strip
                </Field.Label>
            </Field.Field>
        {/if}
    </Popover.Content>
</Popover.Root>

<style>
    .preset {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 2.25rem;
        height: 1.5rem;
    }
    .preset:hover {
        background: var(--color-layer-hover-01);
    }
    .preview {
        display: grid;
        width: 28px;
        height: 18px;
        gap: 1px;
        border: 1px solid var(--color-icon-secondary);
        background: var(--color-icon-secondary);
    }
    .preview i {
        background: var(--color-layer-01);
    }
    .preset[aria-pressed="true"] .preview {
        border-color: var(--color-icon-primary);
        background: var(--color-layer-01);
    }
    .preset[aria-pressed="true"] .preview i {
        background: var(--color-icon-primary);
    }
</style>
