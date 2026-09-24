<script lang="ts">
    import BrowserPicker from "$lib/browser/BrowserPicker.svelte";
    import type { Condition } from "$lib/browser/browserContext.svelte";
    import InstanceComponent from "$lib/browser/InstanceComponent.svelte";
    import { Button } from "$lib/components/ui/button";
    import * as Table from "$lib/components/ui/table";
    import { ApiError, isOutOfDeclaration } from "$lib/api/client";
    import { updateSubTask } from "$lib/data/api";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { SubTaskWithImagesGET } from "../../types/openapi_types";
    import { getContext } from "svelte";
    import { toast } from "svelte-sonner";
    import {
        addSubTaskImage,
        removeSubTaskImage,
        updateSubTaskComments,
    } from "$lib/data/helpers";

    type Props = {
        subtask: SubTaskWithImagesGET;
        taskId: number;
        onAssignmentChange?: () => void | Promise<void>;
    };
    let { subtask, taskId, onAssignmentChange }: Props = $props();

    const globalContext = getContext<GlobalContext>("globalContext");

    const row = $derived(subtask);
    const assigneeId = $derived(row.creator?.id ?? row.creator_id ?? null);
    const isUnassigned = $derived(assigneeId == null);
    const isMine = $derived(assigneeId === globalContext.user.id);

    let showPicker = $state(false);
    let claiming = $state(false);

    const currentImageIds = $derived(row.images.map((img) => String(img.id)));

    const pickerConditions = $derived.by((): Condition[] => {
        const identifiers = new Set<string>();
        for (const img of row.images) {
            if (img.patient?.identifier)
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

    async function claim() {
        claiming = true;
        try {
            await updateSubTask(row.id, { claim: true });
            toast.success("Subtask claimed");
            await onAssignmentChange?.();
        } catch (e) {
            toast.error(e instanceof ApiError ? e.message : String(e));
            await onAssignmentChange?.();
        } finally {
            claiming = false;
        }
    }

    async function unclaim() {
        claiming = true;
        try {
            await updateSubTask(row.id, { claim: false });
            toast.success("Subtask unclaimed");
            await onAssignmentChange?.();
        } catch (e) {
            toast.error(e instanceof ApiError ? e.message : String(e));
            await onAssignmentChange?.();
        } finally {
            claiming = false;
        }
    }

    async function confirmImages(selectedIds: string[]) {
        const initial: string[] = currentImageIds;
        const added = selectedIds.filter((id) => !initial.includes(id));
        const removed = initial.filter((id) => !selectedIds.includes(id));
        try {
            for (const id of removed) {
                await removeSubTaskImage(row.id, id);
            }
            for (const id of added) {
                await addSubTaskImage(row.id, id);
            }
        } catch (e) {
            if (e instanceof ApiError && isOutOfDeclaration(e)) {
                toast.error(e.detail.message, {
                    // The loop above stops at the first refusal, so whatever
                    // ran before it is already saved. Say so, or the grader
                    // re-submits and double-adds those.
                    description:
                        `Image project ${e.detail.image_projects.join(", ")}; ` +
                        `task declares ${e.detail.declared_projects.join(", ")}. ` +
                        `Earlier changes were saved; the rest were not applied.`,
                });
            } else {
                toast.error(String(e));
            }
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
        {#if isUnassigned}
            <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={claiming}
                onclick={claim}
            >
                Claim
            </Button>
        {:else}
            <div class="flex flex-wrap items-center gap-2">
                <span class="text-sm"
                    >{row.creator?.name ?? `Creator #${row.creator_id}`}</span
                >
                {#if isMine}
                    <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={claiming}
                        onclick={unclaim}
                    >
                        Unclaim
                    </Button>
                {/if}
            </div>
        {/if}
    </Table.Cell>
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
            {#if row.images.length > 0}
                {#each row.images as img (img.id)}
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
