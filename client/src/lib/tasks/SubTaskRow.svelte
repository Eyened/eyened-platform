<script lang="ts">
    import { resolve } from "$app/paths";
    import BrowserPicker from "$lib/browser/BrowserPicker.svelte";
    import type { Condition } from "$lib/browser/browserContext.svelte";
    import InstanceComponent from "$lib/browser/InstanceComponent.svelte";
    import { ApiError, isOutOfDeclaration } from "$lib/api/client";
    import { Button } from "$lib/components/ui/button/index.js";
    import { StatusIndicator } from "$lib/components/ui/status-indicator/index.js";
    import * as Table from "$lib/components/ui/table/index.js";
    import { updateSubTask } from "$lib/data/api";
    import { cn } from "$lib/utils.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { addSubTaskImage, removeSubTaskImage } from "$lib/data/helpers";
    import Edit from "carbon-icons-svelte/lib/Edit.svelte";
    import Launch from "carbon-icons-svelte/lib/Launch.svelte";
    import TaskAdd from "carbon-icons-svelte/lib/TaskAdd.svelte";
    import TaskRemove from "carbon-icons-svelte/lib/TaskRemove.svelte";
    import { getContext } from "svelte";
    import type { SubTaskWithImagesGET } from "../../types/openapi_types";
    import { SUBTASK_STATUS } from "./subtaskStatus";

    type Props = {
        subtask: SubTaskWithImagesGET;
        taskId: number;
        /** The table's heading id; the expand header's id derives from it. */
        headingId: string;
        expanded: boolean;
        ontoggle: () => void;
        onedit: (subtask: SubTaskWithImagesGET, button: HTMLElement) => void;
        /** A row action failed; the page shows it and refreshes. */
        onerror: (title: string, subtitle?: string) => void;
        /** A claim or unclaim succeeded, or a save failed; the page refreshes. */
        onchange: () => void | Promise<void>;
    };
    let {
        subtask: row,
        taskId,
        headingId,
        expanded,
        ontoggle,
        onedit,
        onerror,
        onchange,
    }: Props = $props();

    const globalContext = getContext<GlobalContext>("globalContext");

    const assigneeId = $derived(row.creator?.id ?? row.creator_id ?? null);
    const isUnassigned = $derived(assigneeId == null);
    const isMine = $derived(assigneeId === globalContext.user.id);
    const assigneeName = $derived(
        isUnassigned
            ? "Unassigned"
            : (row.creator?.name ?? `Assignee #${assigneeId}`),
    );
    const imageCount = $derived(
        row.images.length === 0
            ? "No images"
            : row.images.length === 1
              ? "1 image"
              : `${row.images.length} images`,
    );
    const expandedId = $derived(`expanded-row-${row.id}`);
    // While expanded, the data cells draw the row's bottom border so the chevron cell joins
    // the expanded row (Carbon expandable).
    const joined = $derived(
        expanded ? "border-b border-border-subtle-01" : undefined,
    );

    let pending = $state(false);
    let showPicker = $state(false);

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

    const message = (e: unknown) =>
        e instanceof Error ? e.message : String(e);

    async function toggleClaim() {
        if (pending) return;
        const claim = isUnassigned;
        pending = true;
        try {
            await updateSubTask(row.id, { claim });
            onchange();
        } catch (e) {
            onerror(
                `Set ${row.index} could not be ${claim ? "claimed" : "unclaimed"}`,
                message(e),
            );
        } finally {
            pending = false;
        }
    }

    // Success or failure, the row is refreshed, so the next save starts from what was saved. On
    // failure the picker stays open with the error and the selection (R1).
    async function confirmImages(selectedIds: string[]) {
        const initial = currentImageIds;
        const added = selectedIds.filter((id) => !initial.includes(id));
        const removed = initial.filter((id) => !selectedIds.includes(id));
        try {
            for (const id of removed) {
                await removeSubTaskImage(row.id, id);
            }
            for (const id of added) {
                await addSubTaskImage(row.id, id);
            }
            await onchange();
        } catch (e) {
            await onchange();
            if (e instanceof ApiError && isOutOfDeclaration(e)) {
                // The loop stops at the first refusal, so whatever ran before it is already saved.
                throw new Error(
                    `${e.detail.message} ` +
                        `Image project ${e.detail.image_projects.join(", ")}; ` +
                        `task declares ${e.detail.declared_projects.join(", ")}. ` +
                        `Earlier changes were saved; the rest were not applied.`,
                    { cause: e }, // eslint preserve-caught-error
                );
            }
            throw e;
        }
    }
</script>

<Table.Row
    class={expanded
        ? "border-b-0 has-[+tr:hover]:bg-layer-hover-01"
        : undefined}
>
    <Table.Cell headers="{headingId}-expand" class="w-10 ps-2 pe-0">
        <Table.ExpandButton
            {expanded}
            {ontoggle}
            aria-label={expanded
                ? "Collapse current row"
                : "Expand current row"}
            aria-controls={expanded ? expandedId : undefined}
        />
    </Table.Cell>
    <Table.Cell class={joined}>
        <!-- 0-based, as the grading viewer shows "Set {index}" -->
        <a
            href={resolve("/tasks/[taskid]/grade/[setid]", {
                taskid: String(taskId),
                setid: String(row.index),
            })}
            target="_blank"
            aria-label="Set {row.index}, opens in a new tab"
            class="inline-flex items-center gap-2 text-link-primary group-hover:text-link-secondary hover:underline"
        >
            {row.index}
            <Launch aria-hidden="true" />
        </a>
    </Table.Cell>
    <Table.Cell class={joined}>
        {#if row.task_state}
            {@const status = SUBTASK_STATUS[row.task_state]}
            <StatusIndicator
                icon={status.icon}
                iconClass={status.iconClass}
                label={status.label}
            />
        {:else}
            —
        {/if}
    </Table.Cell>
    <Table.Cell class={joined}>{assigneeName}</Table.Cell>
    <Table.Cell class={cn("whitespace-nowrap", joined)}>{imageCount}</Table.Cell
    >
    <Table.Cell class={joined}>
        <span class="line-clamp-1">{row.comments || "—"}</span>
    </Table.Cell>
    <!-- Carbon inline row actions: ghost buttons with text and icon in a trailing column. -->
    <Table.Cell class={cn("pe-2 text-end whitespace-nowrap", joined)}>
        {#if isUnassigned || isMine}
            <Button
                variant="ghost"
                aria-label={isUnassigned
                    ? `Claim set ${row.index}`
                    : `Unclaim set ${row.index}`}
                aria-disabled={pending || undefined}
                onclick={toggleClaim}
            >
                {#if isUnassigned}
                    Claim <TaskAdd />
                {:else}
                    Unclaim <TaskRemove />
                {/if}
            </Button>
        {/if}
        <Button
            variant="ghost"
            aria-label="Edit comments for set {row.index}"
            onclick={(e) => onedit(row, e.currentTarget)}
        >
            Edit <Edit />
        </Button>
    </Table.Cell>
</Table.Row>

{#if expanded}
    <Table.ExpandedRow id={expandedId} colspan={7}>
        {#if row.images.length > 0}
            <div class="flex flex-wrap gap-2">
                {#each row.images as img (img.id)}
                    <InstanceComponent instance={img} selectable={false} />
                {/each}
            </div>
        {:else}
            <p class="text-text-secondary">No images</p>
        {/if}
        <Button
            variant="outline"
            size="sm"
            class="mt-4"
            onclick={() => (showPicker = true)}
        >
            Browse images
        </Button>
    </Table.ExpandedRow>
{/if}

{#if showPicker}
    <BrowserPicker
        bind:open={showPicker}
        initialConditions={pickerConditions}
        initialSelectedIds={currentImageIds}
        onConfirm={confirmImages}
        modalLabel="Set {row.index}"
        errorTitle="Images for set {row.index} could not be saved"
    />
{/if}
