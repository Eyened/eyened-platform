<!--
@component
Layers › Pointsets for the selected viewport: this eye's registrations with points on this image, created on it, or current.
The name sets the eye's current registration for every viewport of that eye; P places its points.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
    import {
        createFormAnnotation,
        formAnnotations,
        formSchemasByName,
        instances,
    } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { EyeLaterality } from "$lib/viewer-window/panelRegistration/groupOpenImages";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import Add from "carbon-icons-svelte/lib/Add.svelte";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";
    import { getContext } from "svelte";
    import type { FormAnnotationGET } from "../../types/openapi_types";
    import { imageName } from "$lib/workspace/imageMeta";
    import LayerRow from "./LayerRow.svelte";
    import LayerSection from "./LayerSection.svelte";
    import { eyeKey, imageLines, registrationRows } from "./pointsets";
    import RegistrationDeleteModal from "./RegistrationDeleteModal.svelte";
    import SyncStatus from "./SyncStatus.svelte";

    let { open, ontoggle }: { open: boolean; ontoggle: () => void } = $props();

    const globalContext = getContext<GlobalContext>("globalContext");
    const taskContext = getContext<TaskContext | undefined>("taskContext");
    const workspace = getContext<Workspace>("workspace");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { instance } = viewerContext.image;
    const win = viewerContext.viewerWindowContext;
    const pointsets = win.pointsets;
    const eye = eyeKey(instance);
    let section: HTMLElement | undefined = $state();

    const schemaId = $derived(
        formSchemasByName.get(
            BUILTIN_VIEWER_FORM_SCHEMA_NAMES.POINTSET_REGISTRATION,
        )?.id,
    );
    const currentId = $derived(pointsets.currentId(eye));
    const rows = $derived(
        schemaId === undefined
            ? []
            : registrationRows(formAnnotations.values(), {
                  schemaId,
                  instanceId: instance.id,
                  patientId: instance.patient.id,
                  laterality: (instance.laterality ?? null) as EyeLaterality,
                  currentId,
                  imageLaterality: (id) =>
                      (instances.get(id)?.laterality ?? null) as EyeLaterality,
              }),
    );

    /** This eye's loaded 2D images, in strip order. */
    const loaded = $derived(
        workspace.catalogue.flatMap((id) => {
            const image = win.images.get(id);
            return image?.is2D && eyeKey(image.instance) === eye
                ? [
                      {
                          id: image.instance.id,
                          ...imageName(image.instance, win.twins.get(id) ?? ""),
                      },
                  ]
                : [];
        }),
    );
    // A registration pairs this image with another image of the eye.
    const canCreate = $derived(
        loaded.some((image) => image.id !== instance.id),
    );

    let createError = $state(false);
    async function create() {
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
            pointsets.setCurrent(eye, created.id);
            workspace.arm("point");
        } catch {
            createError = true;
        }
    }

    let deleting: FormAnnotationGET | null = $state(null);
    let deleteOpen = $state(false);
</script>

<div bind:this={section}>
    <LayerSection title="Pointsets" count={rows.length} {open} {ontoggle}>
        {#snippet action()}
            {#if canCreate}
                <Button
                    variant="ghost"
                    size="sm"
                    aria-label="New registration"
                    onclick={create}>New</Button
                >
            {/if}
        {/snippet}
        {#if createError}
            <div class="px-4 py-2">
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
                    {@const current = row.id === currentId}
                    <li>
                        <LayerRow
                            label="Registration [{row.id}]"
                            name="Registration [{row.id}]"
                            selected={current}
                            onselect={() =>
                                pointsets.setCurrent(
                                    eye,
                                    current ? undefined : row.id,
                                )}
                        >
                            {#snippet tags()}
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
                                        onclick={() => {
                                            deleting = row;
                                            deleteOpen = true;
                                        }}
                                    >
                                        <TrashCan />
                                    </IconButton>
                                {/if}
                            {/snippet}
                            {#if current}
                                {@const lines = imageLines(
                                    row.form_data,
                                    instance.id,
                                    loaded,
                                )}
                                <div class="flex flex-col gap-1 ps-8 pe-2 pb-1">
                                    <SyncStatus
                                        sync={pointsets.sync.get(row.id) ??
                                            "synced"}
                                    />
                                    {#if lines}
                                        <ul aria-label="Points per image">
                                            {#each lines as line, i (i)}
                                                <li
                                                    class="flex gap-2 text-body-compact-01"
                                                >
                                                    <span
                                                        class="min-w-0 flex-1 [overflow-wrap:anywhere]"
                                                    >
                                                        <span
                                                            class="block text-text-primary"
                                                            >{line.name}</span
                                                        >
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
                                                            : 'text-text-secondary'}"
                                                        >{line.points}</span
                                                    >
                                                </li>
                                            {/each}
                                        </ul>
                                    {:else}
                                        <p
                                            class="text-body-compact-01 text-text-secondary"
                                        >
                                            No points yet
                                        </p>
                                    {/if}
                                </div>
                            {/if}
                        </LayerRow>
                    </li>
                {/each}
            </ul>
        {:else}
            <Empty.Root class="px-4 py-6">
                <Empty.Header>
                    <!-- ASSUMPTION: the spec asks for a title and a description but gives no text. -->
                    <Empty.Title>No registrations</Empty.Title>
                    <Empty.Description
                        >Create one to place matching points on this image and
                        another of this eye.</Empty.Description
                    >
                </Empty.Header>
                {#if canCreate}
                    <Button variant="ghost" size="sm" onclick={create}
                        >New registration <Add /></Button
                    >
                {/if}
            </Empty.Root>
        {/if}
    </LayerSection>
</div>
<RegistrationDeleteModal
    registration={deleting}
    bind:open={deleteOpen}
    onfallback={() => section?.querySelector<HTMLElement>("button")?.focus()}
/>
