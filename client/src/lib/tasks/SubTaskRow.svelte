<script lang="ts">
    import BrowserPicker from "$lib/browser/BrowserPicker.svelte";
    import type { Condition } from "$lib/browser/browserContext.svelte";
    import InstanceComponent from "$lib/browser/InstanceComponent.svelte";
    import { Button } from "$lib/components/ui/button";
    import * as Table from "$lib/components/ui/table";
    import type { SubTaskWithImagesGET } from "../../types/openapi_types";
    import { toast } from "svelte-sonner";
    import {
        addSubTaskImage,
        removeSubTaskImage,
        updateSubTaskComments,
    } from "$lib/data/helpers";

    type Props = {
        subtask: SubTaskWithImagesGET;
        taskId: number;
    };
    let { subtask, taskId }: Props = $props();

    const row = $derived(subtask);

    let showPicker = $state(false);

    // Image ids currently linked to this subtask.
    const currentImageIds = $derived(
        ((row as any).images ?? []).map((img: any) => String(img.id)),
    );

    // Default query: all images for the patients already linked to this subtask.
    const pickerConditions = $derived.by((): Condition[] => {
        const identifiers = new Set<string>();
        for (const img of (row as any).images ?? []) {
            if (img?.patient?.identifier)
                identifiers.add(img.patient.identifier);
        }
        if (identifiers.size === 0) return [];
        return [
            {
                type: "default",
                variable: "Patient Identifier",
                operator: "IN",
                value: Array.from(identifiers),
            } as Condition,
        ];
    });

    async function confirmImages(selectedIds: string[]) {
        const initial: string[] = currentImageIds;
        const added = selectedIds.filter((id) => !initial.includes(id));
        const removed = initial.filter((id) => !selectedIds.includes(id));
        try {
            // Run sequentially: each endpoint returns a full snapshot of the
            // subtask's images, so parallel requests would ingest out-of-order
            // (stale) snapshots and also race on the next ImageIndex.
            for (const id of removed) {
                await removeSubTaskImage(row.id, id);
            }
            for (const id of added) {
                await addSubTaskImage(row.id, id);
            }
        } catch (e) {
            toast.error(String(e));
        } finally {
            showPicker = false;
        }
    }

    async function removeImage(instance_id: string) {
        try {
            await removeSubTaskImage(row.id, instance_id);
        } catch (e) {
            toast.error(String(e));
        }
    }

    async function updateComments(comments: string) {
        try {
            await updateSubTaskComments(row.id, comments);
        } catch (e) {
            toast.error(String(e));
        }
    }
</script>

<Table.Row>
    <Table.Cell>
        <span class="text-xs">{row.id} [{row.index}]</span>
    </Table.Cell>
    <Table.Cell>{row.task_state ?? "-"}</Table.Cell>
    <Table.Cell>
        <Button
            href={`/tasks/${taskId}/grade/${row.index}`}
            target="_blank"
            class="rounded bg-blue-500 px-2 py-1 text-white hover:bg-blue-600"
        >
            View
        </Button>
    </Table.Cell>
    <Table.Cell>
        <div class="instances flex flex-wrap gap-1">
            {#if (row as any).images?.length > 0}
                {#each (row as any).images as img}
                    <div class="relative inline-block">
                        <InstanceComponent instance={img} />
                        <button
                            class="absolute -top-1 -right-1 z-10 h-6 w-6 rounded-full bg-red-600 text-center text-xs leading-6 text-white shadow hover:bg-red-700"
                            onclick={(e) => {
                                e.stopPropagation();
                                removeImage(img.id);
                            }}
                            aria-label="Remove image"
                            title="Remove image"
                            type="button"
                        >
                            ×
                        </button>
                    </div>
                {/each}
            {:else}
                -
            {/if}

            <div class="mt-1 w-full">
                <Button type="button" onclick={() => (showPicker = true)}>
                    Browse images
                </Button>
            </div>
        </div>
    </Table.Cell>
    <Table.Cell>
        <textarea
            value={row.comments || ""}
            onchange={async (e) => {
                const target = e.target as HTMLTextAreaElement;
                await updateComments(target.value);
            }}
            class="min-h-[60px] w-full rounded border p-2"
            placeholder="Add comments..."
        ></textarea>
    </Table.Cell>
</Table.Row>

{#if showPicker}
    <BrowserPicker
        initialConditions={pickerConditions}
        initialSelectedIds={currentImageIds}
        onConfirm={confirmImages}
        onCancel={() => (showPicker = false)}
        confirmLabel="Save images"
        title={`Select images for subtask [${row.index}]`}
    />
{/if}

<style>
    .instances {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
    }
</style>
