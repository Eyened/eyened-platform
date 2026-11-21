<!--
@component
The Selected pane for an ETDRS grid: creator, fovea and disc edge as text, and "This task". Place ETDRS (G) places the points.
-->
<script lang="ts">
    import { Tag } from "$lib/components/ui/tag/index.js";
    import { formAnnotations } from "$lib/data";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { Position2D } from "$lib/types";
    import { getContext, type Snippet } from "svelte";
    import { isThisTask } from "../gridLayers.svelte";
    import PaneFields from "./PaneFields.svelte";
    import PaneHeader from "./PaneHeader.svelte";

    let {
        id,
        gridId,
        remove,
    }: { id: string; gridId: number; remove?: Snippet } = $props();
    const taskContext = getContext<TaskContext | undefined>("taskContext");
    // SelectedPane mounts this only while the grid exists.
    const grid = $derived(formAnnotations.get(gridId)!);
    const data = $derived(
        (grid.form_data ?? {}) as Record<string, Position2D | undefined>,
    );
    const coords = (p: Position2D | undefined) =>
        p ? `${Math.round(p.x)}, ${Math.round(p.y)}` : "—";
    const rows = $derived<[string, string][]>([
        ["Creator", grid.creator.name],
        ["Fovea", coords(data.fovea)],
        ["Disc edge", coords(data.disc_edge)],
    ]);
</script>

<PaneHeader
    {id}
    name="ETDRS grid, {grid.creator.name}"
    type="ETDRS grid"
    {remove}
>
    {#snippet status()}
        {#if isThisTask(grid, taskContext?.subTask?.id)}
            <Tag>This task</Tag>
        {/if}
    {/snippet}
</PaneHeader>
<div class="min-h-0 flex-1 overflow-y-auto py-2">
    <PaneFields {rows} />
</div>
