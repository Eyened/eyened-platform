<!--
@component
A plain list of the catalogue until sub-project 6: patient headings, a visit heading each time the date changes.
Click loads into the selected viewport; drag loads onto any viewport.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { getContext } from "svelte";
    import { IMAGE_MIME } from "./dragTypes";
    import type { ViewportTitle } from "./imageMeta";
    import type { Workspace } from "./workspace.svelte";

    let {
        titleFor,
        onaddimages,
        onloaded,
    }: {
        titleFor: (imageId: string) => ViewportTitle | null;
        onaddimages: () => void;
        onloaded: () => void;
    } = $props();

    const workspace = getContext<Workspace>("workspace");
    const inView = $derived(workspace.slots.map((slot) => slot.imageId));

    type Visit = { date: string; images: string[] };
    type PatientGroup = { patient: string; visits: Visit[] };

    // ASSUMPTION: groups follow catalogue order (plan decision 15).
    const groups = $derived.by(() => {
        const out: PatientGroup[] = [];
        for (const e of workspace.entries) {
            let group = out.at(-1);
            if (!group || group.patient !== e.patient) {
                group = { patient: e.patient, visits: [] };
                out.push(group);
            }
            let visit = group.visits.at(-1);
            if (!visit || visit.date !== e.date) {
                visit = { date: e.date, images: [] };
                group.visits.push(visit);
            }
            visit.images.push(e.imageId);
        }
        return out;
    });

    function load(imageId: string) {
        workspace.load(workspace.selected, imageId);
        onloaded();
    }

    function ondragstart(e: DragEvent, imageId: string) {
        if (!e.dataTransfer) return;
        e.dataTransfer.setData(IMAGE_MIME, imageId);
        e.dataTransfer.effectAllowed = "copy";
    }
</script>

<div class="flex flex-col gap-2 p-2">
    <Button variant="ghost" size="sm" onclick={onaddimages}>Add images…</Button>
    {#each groups as group, g (g)}
        <h3 class="px-2 text-heading-compact-01 text-text-primary">
            {group.patient}
        </h3>
        {#each group.visits as visit, v (v)}
            <h4 class="px-2 text-label-01 text-text-secondary">{visit.date}</h4>
            <ul class="flex flex-col">
                {#each visit.images as imageId (imageId)}
                    <li>
                        <button
                            type="button"
                            draggable="true"
                            class="flex min-h-8 w-full items-center justify-between gap-2 px-2 text-start text-body-compact-01 text-text-primary hover:bg-layer-hover-01"
                            onclick={() => load(imageId)}
                            ondragstart={(e) => ondragstart(e, imageId)}
                        >
                            <span class="min-w-0 truncate"
                                >{titleFor(imageId)?.rest ?? imageId}</span
                            >
                            {#if inView.includes(imageId)}
                                <span
                                    class="flex-none text-label-01 text-text-secondary"
                                    >In view</span
                                >
                            {/if}
                        </button>
                    </li>
                {/each}
            </ul>
        {/each}
    {/each}
</div>
