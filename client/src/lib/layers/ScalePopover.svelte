<!--
@component
The scale button for Distance and the ETDRS circle: the value and its source, and a popover to pick the source for this image.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import { RadioButton } from "$lib/components/ui/radio-button/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type {
        LayersTarget,
        Workspace,
    } from "$lib/workspace/workspace.svelte";
    import ChevronDown from "carbon-icons-svelte/lib/ChevronDown.svelte";
    import { getContext } from "svelte";
    import CommitNumberInput from "./CommitNumberInput.svelte";
    import { AI_GRID } from "./gridLayers.svelte";
    import {
        gridScale,
        perPixel,
        scaleText,
        type ScalePick,
    } from "./imageScale";

    let {
        layers,
        empty,
    }: {
        layers: Pick<LayersTarget, "viewerContext" | "grids" | "scale">;
        /** The button's text when nothing gives a scale. */
        empty: string;
    } = $props();

    const uid = $props.id();
    const workspace = getContext<Workspace>("workspace");
    const globalContext = getContext<GlobalContext>("globalContext");
    let open = $state(false);
    const image = $derived(layers.viewerContext.image);
    const scale = $derived(layers.scale);
    const label = $derived(scale ? scaleText(scale) : empty);
    const stored = $derived(
        image.resolution.x > 0 && image.resolution.y > 0
            ? image.resolution
            : null,
    );
    const valueOf = (pick: ScalePick) =>
        pick.kind === "grid" ? `grid:${pick.key}` : pick.kind;
    // A pick stays selected even when it gives no scale.
    const chosen = $derived(
        workspace.scalePicks.get(image.image_id) ?? scale?.pick,
    );
    const selected = $derived(chosen ? valueOf(chosen) : "");
    // The typed fields start from the scale in use, to two decimals.
    const typed = $derived(
        scale
            ? { x: Number(scale.x.toFixed(2)), y: Number(scale.y.toFixed(2)) }
            : { x: 0, y: 0 },
    );

    // Your grids first, then the AI grid, then other graders'; each group oldest first.
    const grids = $derived.by(() => {
        const byId = new Map(layers.grids.list().map((g) => [g.id, g]));
        return layers.grids
            .scaleGrids()
            .map((grid) => {
                const annotation =
                    grid.key === AI_GRID ? undefined : byId.get(grid.key);
                const mine = annotation?.creator.id === globalContext.user.id;
                const name =
                    grid.key === AI_GRID
                        ? "AI grid"
                        : mine
                          ? `Your grid ${grid.key}`
                          : `${annotation?.creator.name}'s grid ${grid.key}`;
                return {
                    key: grid.key,
                    name:
                        grid.key === layers.grids.currentId
                            ? `${name} (current)`
                            : name,
                    value: gridScale(grid, workspace.etdrsFraction),
                    rank: mine ? 0 : grid.key === AI_GRID ? 1 : 2,
                };
            })
            .sort((a, b) => a.rank - b.rank);
    });

    function choose(pick: ScalePick) {
        workspace.scalePicks.set(image.image_id, pick);
    }
</script>

<Popover.Root bind:open>
    <Popover.Trigger>
        {#snippet child({ props })}
            <Button
                {...props}
                variant="ghost"
                size="sm"
                class="tabular-nums"
                aria-label="Scale: {label}">{label} <ChevronDown /></Button
            >
        {/snippet}
    </Popover.Trigger>
    <Popover.Content
        align="start"
        aria-label="Scale for this image"
        class="flex w-80 flex-col gap-2 p-4"
    >
        <fieldset class="flex flex-col gap-2">
            <legend class="mb-2 text-heading-compact-01 text-text-primary"
                >Scale for this image</legend
            >
            {#if stored}
                <RadioButton
                    name={uid}
                    value="stored"
                    labelText="Stored resolution · {perPixel(
                        stored.x,
                        stored.y,
                    )}"
                    checked={selected === "stored"}
                    onchange={() => choose({ kind: "stored" })}
                />
            {:else}
                <p class="text-body-compact-01 text-text-secondary">
                    Stored resolution — none
                </p>
            {/if}
            {#each grids as grid (grid.key)}
                {#if grid.value || selected === `grid:${grid.key}`}
                    <RadioButton
                        name={uid}
                        value="grid:{grid.key}"
                        labelText="{grid.name} · {grid.value
                            ? perPixel(grid.value, grid.value)
                            : 'needs both points'}"
                        checked={selected === `grid:${grid.key}`}
                        onchange={() => choose({ kind: "grid", key: grid.key })}
                    />
                {:else}
                    <p class="text-body-compact-01 text-text-secondary">
                        {grid.name} · needs both points
                    </p>
                {/if}
            {/each}
            <RadioButton
                name={uid}
                value="typed"
                labelText="Typed"
                checked={selected === "typed"}
                onchange={() => choose({ kind: "typed", ...typed })}
            />
            <div class="flex flex-col gap-2 ps-7">
                <CommitNumberInput
                    labelText="X (µm/px)"
                    value={typed.x}
                    step={0.1}
                    oncommit={(x) =>
                        choose({
                            kind: "typed",
                            x,
                            y: typed.y > 0 ? typed.y : x,
                        })}
                />
                <CommitNumberInput
                    labelText="Y (µm/px)"
                    value={typed.y}
                    step={0.1}
                    oncommit={(y) =>
                        choose({
                            kind: "typed",
                            x: typed.x > 0 ? typed.x : y,
                            y,
                        })}
                />
            </div>
        </fieldset>
        <p
            class="border-t border-border-subtle-01 pt-2 text-helper-text-01 text-text-secondary"
        >
            From a grid: fovea to disc edge × {workspace.etdrsFraction} = 3 mm. Fraction
            is set in ETDRS grids.
        </p>
    </Popover.Content>
</Popover.Root>
