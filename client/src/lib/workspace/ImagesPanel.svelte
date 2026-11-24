<!--
@component
The Images panel: the catalogue as a listbox, in catalogue order, with a patient heading and a visit heading each time they change.
One tab stop: ↑ ↓ Home End move without loading; Enter or Space, or a click, loads into the selected viewport; a drag loads onto any viewport.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import { getThumbUrl } from "$lib/data-loading/utils";
    import { getContext, tick } from "svelte";
    import { SvelteSet } from "svelte/reactivity";
    import type { ImageGET } from "../../types/openapi_types";
    import { IMAGE_MIME } from "./dragTypes";
    import {
        deviceText,
        imageRowName,
        octPart,
        type ViewportTitle,
    } from "./imageMeta";
    import { rovingIndex } from "./rovingIndex";
    import type { Workspace } from "./workspace.svelte";

    let {
        titleFor,
        instanceFor,
        onaddimages,
        onloaded,
    }: {
        titleFor: (imageId: string) => ViewportTitle | null;
        instanceFor: (imageId: string) => ImageGET | null;
        onaddimages: () => void;
        onloaded: () => void;
    } = $props();

    const workspace = getContext<Workspace>("workspace");
    const uid = $props.id();
    let list: HTMLElement | undefined = $state();

    type Run = {
        patient: string;
        /** The id of the patient heading this run sits under, which an earlier run may hold. */
        patientId: string;
        showPatient: boolean;
        date: string;
        dateId: string;
        images: string[];
    };
    // A listbox can't hold headings, so each run of one patient and one visit is a group named by its two visible headings.
    const runs = $derived.by(() => {
        const out: Run[] = [];
        for (const e of workspace.entries) {
            const last = out.at(-1);
            if (last && last.patient === e.patient && last.date === e.date) {
                last.images.push(e.imageId);
                continue;
            }
            const showPatient = !last || last.patient !== e.patient;
            out.push({
                patient: e.patient,
                patientId: showPatient
                    ? `${uid}-patient-${out.length}`
                    : (last?.patientId ?? ""),
                showPatient,
                date: e.date,
                dateId: `${uid}-date-${out.length}`,
                images: [e.imageId],
            });
        }
        return out;
    });
    const order = $derived(runs.flatMap((run) => run.images));
    const selectedImage = $derived(
        workspace.slots[workspace.selected]?.imageId ?? null,
    );
    /** The last focused option; the tab stop falls back to the selected viewport's image, then the first. */
    let focusId: string | null = $state(null);
    const tabStop = $derived(
        focusId !== null && order.includes(focusId)
            ? focusId
            : selectedImage !== null && order.includes(selectedImage)
              ? selectedImage
              : (order[0] ?? null),
    );
    /** 1-based numbers of the slots showing each image. */
    const slotNumbers = $derived(
        workspace.slots.reduce<Record<string, number[]>>(
            (out, slot, i) =>
                slot.imageId
                    ? {
                          ...out,
                          [slot.imageId]: [...(out[slot.imageId] ?? []), i + 1],
                      }
                    : out,
            {},
        ),
    );
    /** Instances whose thumbnail failed (none stored, 422); their rows show a grey box. */
    const failed = new SvelteSet<string>();

    function load(imageId: string) {
        workspace.load(workspace.selected, imageId);
        onloaded();
    }

    // Focus moving never loads: selection following focus would replace the viewport's image on every arrow.
    async function onkeydown(e: KeyboardEvent, imageId: string) {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            load(imageId);
            return;
        }
        const next = rovingIndex(e.key, order.indexOf(imageId), order.length, {
            prev: ["ArrowUp"],
            next: ["ArrowDown"],
        });
        if (next === null) return;
        e.preventDefault();
        focusId = order[next];
        await tick();
        list?.querySelector<HTMLElement>(`[data-index="${next}"]`)?.focus();
    }

    function ondragstart(e: DragEvent, imageId: string) {
        if (!e.dataTransfer) return;
        e.dataTransfer.setData(IMAGE_MIME, imageId);
        e.dataTransfer.effectAllowed = "copy";
    }
</script>

<div class="flex flex-col gap-2 pb-2">
    <Button
        variant="ghost"
        size="sm"
        class="mx-2 self-start"
        onclick={onaddimages}>Add images…</Button
    >
    <div
        role="listbox"
        aria-label="Images"
        bind:this={list}
        onfocusout={(e) => {
            // Leaving the list: the next Tab lands on the selected viewport's image again.
            if (!list?.contains(e.relatedTarget as Node)) focusId = null;
        }}
    >
        {#each runs as run (run.dateId)}
            <div role="group" aria-labelledby="{run.patientId} {run.dateId}">
                {#if run.showPatient}
                    <div
                        id={run.patientId}
                        aria-hidden="true"
                        class="px-4 pt-3 pb-1 text-heading-compact-01 text-text-primary"
                    >
                        {run.patient}
                    </div>
                {/if}
                <div
                    id={run.dateId}
                    aria-hidden="true"
                    class="px-4 pt-2 pb-1 text-label-01 text-text-secondary"
                >
                    {run.date}
                </div>
                {#each run.images as imageId (imageId)}
                    {@const meta = instanceFor(imageId)}
                    {@const twin = titleFor(imageId)?.twin}
                    {@const slots = slotNumbers[imageId]}
                    {@const device = meta ? deviceText(meta) : ""}
                    <div
                        role="option"
                        tabindex={imageId === tabStop ? 0 : -1}
                        aria-selected={imageId === selectedImage}
                        draggable="true"
                        data-index={order.indexOf(imageId)}
                        class="flex min-h-16 cursor-pointer items-center gap-2 py-2 ps-4 pe-2 hover:bg-layer-hover-01 aria-selected:selected-look aria-selected:hover:bg-layer-selected-hover-01"
                        onclick={() => load(imageId)}
                        onkeydown={(e) => onkeydown(e, imageId)}
                        onfocus={() => (focusId = imageId)}
                        ondragstart={(e) => ondragstart(e, imageId)}
                    >
                        {#if meta && !failed.has(meta.id)}
                            <img
                                src={getThumbUrl(meta, 144)}
                                alt=""
                                loading="lazy"
                                width="48"
                                height="48"
                                class="size-12 flex-none object-cover"
                                onerror={() => failed.add(meta.id)}
                            />
                        {:else}
                            <span
                                aria-hidden="true"
                                class="size-12 flex-none bg-layer-accent-01"
                            ></span>
                        {/if}
                        <span class="flex min-w-0 flex-1 flex-col">
                            <span
                                class="flex min-w-0 gap-1 text-body-compact-01 text-text-primary"
                            >
                                <span class="min-w-0 truncate"
                                    >{meta
                                        ? imageRowName(
                                              meta,
                                              octPart(imageId, (id) =>
                                                  order.includes(id),
                                              ),
                                          )
                                        : imageId}</span
                                >
                                {#if twin}
                                    <span class="flex-none">{twin}</span>
                                {/if}
                            </span>
                            {#if device}
                                <span
                                    class="truncate text-label-01 text-text-secondary"
                                    >{device}</span
                                >
                            {/if}
                        </span>
                        {#if slots}
                            <Tag type="blue" class="flex-none"
                                ><span class="sr-only">in viewport</span>
                                {slots.join(", ")}</Tag
                            >
                        {:else}
                            <span
                                class="flex-none text-label-01 text-text-secondary"
                                >Not in view</span
                            >
                        {/if}
                    </div>
                {/each}
            </div>
        {/each}
    </div>
</div>
