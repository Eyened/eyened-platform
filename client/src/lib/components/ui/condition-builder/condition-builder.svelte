<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import Add from "carbon-icons-svelte/lib/Add.svelte";
    import { tick } from "svelte";
    import ConditionRow from "./condition-row.svelte";
    import { move, rowCells, type Cell } from "./grid-navigation.js";
    import type { BuilderProperty, BuilderRow } from "./types.js";

    // IBM Products ConditionBuilder, Non-Hierarchical, rebuilt in Svelte: behaviour from
    // @carbon/ibm-products 2.99.0, values from @carbon/ibm-products-styles 2.95.0. Conditions flow
    // inline and wrap; the grid is one Tab stop with a roving tabindex (ARIA grid).
    const uid = $props.id();
    let {
        properties,
        rows = $bindable([]),
        label = "Search conditions",
    }: {
        properties: BuilderProperty[];
        rows?: BuilderRow[];
        label?: string;
    } = $props();

    const ARROWS = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"];
    let grid = $state<HTMLElement | null>(null);
    let addButton = $state<HTMLElement | null>(null);
    let active = $state<{ rowId: number; cell: Cell } | null>(null);
    let openRowId = $state<number | null>(null);
    let announcement = $state("");

    const cells = $derived(
        rows.map((r, i) => rowCells(r, properties, i === rows.length - 1)),
    );
    // The Tab stop: the last focused cell, or the first property once that cell is gone.
    const tabStop = $derived.by(() => {
        const i = active ? rows.findIndex((r) => r.id === active?.rowId) : -1;
        if (active && i !== -1 && cells[i].includes(active.cell)) return active;
        return rows[0] ? { rowId: rows[0].id, cell: "property" as Cell } : null;
    });

    function addRow(after: number) {
        const id = Math.max(0, ...rows.map((r) => r.id)) + 1;
        rows = [...rows.slice(0, after + 1), { id }, ...rows.slice(after + 1)];
        openRowId = id;
    }

    function updateRow(next: BuilderRow) {
        rows = rows.map((r) => (r.id === next.id ? next : r));
    }

    async function removeRow(index: number) {
        rows = rows.filter((_, i) => i !== index);
        announcement = "";
        await tick();
        announcement = "Condition removed";
        if (rows.length > 0)
            focusCell(Math.min(index, rows.length - 1), "delete");
        else addButton?.focus();
    }

    function focusCell(row: number, cell: Cell) {
        grid?.querySelector<HTMLElement>(
            `[data-row="${row}"][data-cell="${cell}"]`,
        )?.focus();
    }

    function onkeydown(e: KeyboardEvent) {
        const target = e.target as HTMLElement;
        const cell = target.dataset.cell as Cell | undefined;
        if (!cell || !ARROWS.includes(e.key)) return;
        e.preventDefault();
        const next = move(
            cells,
            { row: Number(target.dataset.row), cell },
            e.key,
        );
        if (next) focusCell(next.row, next.cell);
    }

    function onfocusin(e: FocusEvent) {
        const target = e.target as HTMLElement;
        const cell = target.dataset.cell as Cell | undefined;
        const row = rows[Number(target.dataset.row)];
        if (cell && row) active = { rowId: row.id, cell };
    }
</script>

<Tooltip.Provider delayDuration={100}>
    {#if rows.length === 0}
        <Button
            variant="ghost"
            size="sm"
            bind:ref={addButton}
            onclick={() => addRow(-1)}
        >
            Add condition <Add />
        </Button>
    {:else}
        <!-- tabindex -1: a grid with key handlers must be focusable; the cells hold the Tab stop. -->
        <div
            bind:this={grid}
            role="grid"
            tabindex="-1"
            aria-label={label}
            aria-describedby="{uid}-help"
            class="flex flex-wrap text-body-01"
            {onkeydown}
            {onfocusin}
        >
            {#each rows as row, i (row.id)}
                <ConditionRow
                    {row}
                    index={i}
                    {properties}
                    cells={cells[i]}
                    tabStop={tabStop?.rowId === row.id ? tabStop.cell : null}
                    openOnMount={openRowId === row.id}
                    onchange={updateRow}
                    onremove={() => removeRow(i)}
                    onadd={() => addRow(i)}
                />
            {/each}
        </div>
    {/if}
    <p id="{uid}-help" class="sr-only">
        Each condition has a property, an operator and a value. Arrow keys move
        between parts and conditions; Enter or Space changes a part.
    </p>
    <div role="status" class="sr-only">{announcement}</div>
</Tooltip.Provider>
