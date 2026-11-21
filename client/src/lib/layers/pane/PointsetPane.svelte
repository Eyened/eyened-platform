<!--
@component
The Selected pane for a pointset: its save state, then its points per image. Edit with arms Point (P).
-->
<script lang="ts">
    import EditWith from "./EditWith.svelte";
    import { formAnnotations } from "$lib/data";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import { getContext, type Snippet } from "svelte";
    import { eyeKey, imageLines, loadedEyeImages } from "../pointsets";
    import SyncStatus from "../SyncStatus.svelte";
    import PaneHeader from "./PaneHeader.svelte";

    let {
        id,
        pointsetId,
        remove,
    }: { id: string; pointsetId: number; remove?: Snippet } = $props();
    const workspace = getContext<Workspace>("workspace");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { instance } = viewerContext.image;
    const win = viewerContext.viewerWindowContext;
    const eye = eyeKey(instance);
    // SelectedPane mounts this only while the pointset exists.
    const row = $derived(formAnnotations.get(pointsetId)!);
    const loaded = $derived(loadedEyeImages(workspace.catalogue, win, eye));
    const lines = $derived(imageLines(row.form_data, instance.id, loaded));
</script>

<PaneHeader {id} name="Registration [{pointsetId}]" type="Pointset" {remove}>
    {#snippet status()}
        <SyncStatus sync={win.pointsets.sync.get(pointsetId) ?? "synced"} />
    {/snippet}
</PaneHeader>
<div class="min-h-0 flex-1 overflow-y-auto px-4 py-2">
    {#if lines}
        <p id="{id}-points" class="text-label-01 text-text-secondary">
            Points per image
        </p>
        <ul aria-labelledby="{id}-points">
            {#each lines as line, i (i)}
                <li class="flex gap-2 text-body-compact-01">
                    <span class="min-w-0 flex-1 wrap-anywhere">
                        <span class="block text-text-primary">{line.name}</span>
                        {#if line.device}
                            <span
                                class="block text-label-01 text-text-secondary"
                                >{line.device}</span
                            >
                        {/if}
                    </span>
                    <span
                        class="tabular-nums {line.gap
                            ? 'text-text-error'
                            : 'text-text-secondary'}">{line.points}</span
                    >
                </li>
            {/each}
        </ul>
    {:else}
        <p class="text-body-compact-01 text-text-secondary">No points yet</p>
    {/if}
</div>
{#if remove}<EditWith tool="point" />{/if}
