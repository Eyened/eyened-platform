<!--
@component
Layers › Pointsets for the selected viewport: this eye's registrations with points on this image, created on it, or current.
A row selects the pointset P edits in this viewport; the eye's registration in use is set in Display › Registration.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import { createFormAnnotation } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import Add from "carbon-icons-svelte/lib/Add.svelte";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";
    import { getContext } from "svelte";
    import type { FormAnnotationGET } from "../../types/openapi_types";
    import LayerRow from "./LayerRow.svelte";
    import LayerSection from "./LayerSection.svelte";
    import { focusAfterDelete } from "./focusAfterDelete";
    import {
        eyeKey,
        eyeRegistrationRows,
        eyeSuffix,
        loadedEyeImages,
        registrationSchemaId,
    } from "./pointsets";
    import RegistrationDeleteModal from "./RegistrationDeleteModal.svelte";

    let { open, ontoggle }: { open: boolean; ontoggle: () => void } = $props();

    const globalContext = getContext<GlobalContext>("globalContext");
    const taskContext = getContext<TaskContext | undefined>("taskContext");
    const workspace = getContext<Workspace>("workspace");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { instance } = viewerContext.image;
    const { selection } = getContext<MainViewerContext>("mainViewerContext");
    const win = viewerContext.viewerWindowContext;
    const pointsets = win.pointsets;
    const eye = eyeKey(instance);
    let section: HTMLElement | undefined = $state();

    const inUseId = $derived(pointsets.currentId(eye));
    const rows = $derived(eyeRegistrationRows(instance, inUseId));

    const loaded = $derived(loadedEyeImages(workspace.catalogue, win, eye));
    // A registration pairs this image with another image of the eye.
    const canCreate = $derived(
        loaded.some((image) => image.id !== instance.id),
    );

    let createError = $state(false);
    async function create() {
        const schemaId = registrationSchemaId();
        if (schemaId === undefined) return;
        createError = false;
        if (!open) ontoggle();
        try {
            const created = await createFormAnnotation({
                form_schema_id: schemaId,
                patient_id: instance.patient.id,
                study_id: instance.study?.id ?? undefined,
                image_id: instance.id,
                laterality: instance.laterality ?? undefined,
                sub_task_id: taskContext?.subTask?.id,
                form_data: {},
            });
            // New selects what it makes; it is put in use only when the eye has none.
            selection.select({ kind: "pointset", id: created.id });
            if (pointsets.currentId(eye) === undefined)
                pointsets.setCurrent(eye, created.id);
            workspace.arm("point");
        } catch {
            createError = true;
        }
    }

    let deleting: FormAnnotationGET | null = $state(null);
    let deleteOpen = $state(false);
    let fallback = () => {};
</script>

<div bind:this={section} data-layer-section="pointsets">
    <LayerSection
        title="Pointsets"
        count={rows.length}
        {open}
        {ontoggle}
        empty={canCreate
            ? "Use + to place matching points on this image and another of this eye."
            : "Open another image of this eye to add one."}
    >
        {#snippet action()}
            {#if canCreate}
                <IconButton
                    size="icon-xs"
                    variant="secondary"
                    label="New registration"
                    onclick={create}><Add /></IconButton
                >
            {/if}
        {/snippet}
        {#if createError}
            <div class="py-2 ps-8 pe-4">
                <InlineNotification
                    title="Couldn't create a registration"
                    subtitle="Try again."
                    role="status"
                />
            </div>
        {/if}
        {#if rows.length > 0}
            <ul>
                {#each rows as row (row.id)}
                    {@const current = selection.pointsetId() === row.id}
                    <li>
                        <LayerRow
                            label="Registration [{row.id}]"
                            name="Registration [{row.id}]"
                            selected={current}
                            onselect={() =>
                                selection.select(
                                    current
                                        ? null
                                        : { kind: "pointset", id: row.id },
                                )}
                        >
                            {#snippet tags()}
                                {#if row.id === inUseId}<Tag
                                        >In use{eyeSuffix(
                                            instance.laterality,
                                        )}</Tag
                                    >{/if}
                                <Tag
                                    >{row.creator.id === globalContext.user.id
                                        ? "Mine"
                                        : row.creator.name}</Tag
                                >
                            {/snippet}
                            {#snippet icons()}
                                {#if globalContext.canEdit(row)}
                                    <IconButton
                                        size="icon-xs"
                                        label="Delete"
                                        onclick={(e) => {
                                            fallback = focusAfterDelete(
                                                (
                                                    e.currentTarget as Element
                                                ).closest("[data-layer-row]"),
                                                section ?? null,
                                            );
                                            deleting = row;
                                            deleteOpen = true;
                                        }}
                                    >
                                        <TrashCan />
                                    </IconButton>
                                {/if}
                            {/snippet}
                        </LayerRow>
                    </li>
                {/each}
            </ul>
        {/if}
    </LayerSection>
</div>
<RegistrationDeleteModal
    registration={deleting}
    bind:open={deleteOpen}
    onfallback={() => fallback()}
/>
