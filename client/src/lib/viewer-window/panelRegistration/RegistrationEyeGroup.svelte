<script lang="ts">
    import Button from "$lib/components/ui/button/button.svelte";
    import {
        createFormAnnotation,
        deleteFormAnnotation,
        formAnnotations,
        instances,
    } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import { getContext } from "svelte";
    import type { FormSchemaGET } from "../../../types/openapi_types";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import RegistrationItem from "./RegistrationItem.svelte";
    import RegistrationThumbs from "./RegistrationThumbs.svelte";
    import {
        annotationMatchesEye,
        canOpenRegistration,
        groupKey,
        type EyeGroup,
        type OpenImage,
    } from "./groupOpenImages";

    interface Props {
        group: EyeGroup;
        registrationSchema: FormSchemaGET;
    }

    const { group, registrationSchema }: Props = $props();

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );
    const taskContext = getContext<TaskContext | undefined>("taskContext");
    const globalContext = getContext<GlobalContext>("globalContext");

    const key = $derived(groupKey(group.patientId, group.laterality));

    let fixedId = $state("");
    let movingId = $state("");
    let choice = $state("");
    let blendIds = $state<string[]>([]);
    let creating = $state(false);

    const existing = $derived(
        formAnnotations.filter(
            (annotation) =>
                annotationMatchesEye(
                    annotation,
                    registrationSchema.id,
                    group.patientId,
                    group.laterality,
                    (imageId) => instances.get(imageId)?.laterality ?? null,
                ) && globalContext.canEdit(annotation),
        ),
    );

    $effect(() => {
        const ids = existing.map((annotation) => String(annotation.id));
        if (!ids.includes(choice)) {
            choice = ids[0] ?? "";
        }
    });

    const selectedBlendIds = $derived.by(() => {
        const selected = new Set(blendIds);
        return group.images
            .filter((image) => selected.has(image.imageId))
            .map((image) => image.imageId);
    });

    function imageInGroup(imageId: string): OpenImage | undefined {
        return group.images.find((image) => image.imageId === imageId);
    }

    function setFixed(imageId: string) {
        if (movingId === imageId) movingId = "";
        fixedId = imageId;
    }

    function setMoving(imageId: string) {
        if (fixedId === imageId) fixedId = "";
        movingId = imageId;
    }

    function toggleBlend(imageId: string) {
        blendIds = blendIds.includes(imageId)
            ? blendIds.filter((id) => id !== imageId)
            : [...blendIds, imageId];
    }

    function viewBlend() {
        if (selectedBlendIds.length < 2) return;
        viewerWindowContext.openSeriesBlend({ imageIds: selectedBlendIds });
    }

    function selectedPair() {
        if (!canOpenRegistration(fixedId, movingId)) return null;
        const fixed = imageInGroup(fixedId);
        const moving = imageInGroup(movingId);
        if (!fixed || !moving) return null;
        return { fixed, moving };
    }

    function openExisting() {
        const pair = selectedPair();
        if (!pair || !choice) return;
        viewerWindowContext.openRegistrationEditor({
            imageIds: [pair.fixed.imageId, pair.moving.imageId],
            annotationId: Number(choice),
        });
    }

    async function openNew() {
        const pair = selectedPair();
        if (!pair || creating) return;
        creating = true;
        try {
            const created = await createFormAnnotation({
                form_schema_id: registrationSchema.id,
                patient_id: group.patientId,
                image_id: pair.fixed.instanceId,
                study_id: pair.fixed.studyId,
                sub_task_id: taskContext?.subTask?.id,
                form_data: {},
                ...(group.laterality != null
                    ? { laterality: group.laterality }
                    : {}),
            });
            viewerWindowContext.openRegistrationEditor({
                imageIds: [pair.fixed.imageId, pair.moving.imageId],
                annotationId: created.id,
            });
        } catch {
            return;
        } finally {
            creating = false;
        }
    }
</script>

<div class="tile">
    <RegistrationThumbs
        label="Fixed"
        images={group.images}
        selectedIds={fixedId ? [fixedId] : []}
        ariaRole="Fixed"
        onSelect={setFixed}
    />
    <RegistrationThumbs
        label="Moving"
        images={group.images}
        selectedIds={movingId ? [movingId] : []}
        ariaRole="Moving"
        onSelect={setMoving}
    />
    {#if existing.length}
        <div class="role">
            <div class="role-label" id="existing-{key}">
                Existing registrations:
            </div>
            <ul class="existing" aria-labelledby="existing-{key}">
                {#each existing as annotation (annotation.id)}
                    <RegistrationItem
                        formAnnotation={annotation}
                        active={choice === String(annotation.id)}
                        onactivate={() => (choice = String(annotation.id))}
                        onremove={() => deleteFormAnnotation(annotation.id)}
                    />
                {/each}
            </ul>
            <Button
                size="sm"
                disabled={!canOpenRegistration(fixedId, movingId) ||
                    !choice ||
                    creating}
                onclick={openExisting}
            >
                Open
            </Button>
        </div>
    {/if}
    <Button
        size="sm"
        class="mt-1.5"
        disabled={!canOpenRegistration(fixedId, movingId) || creating}
        onclick={openNew}
    >
        Create new registration
    </Button>
</div>
<div class="tile">
    <RegistrationThumbs
        label="Blend"
        images={group.images}
        selectedIds={selectedBlendIds}
        ariaRole="Blend"
        onSelect={toggleBlend}
    >
        <Button
            size="sm"
            class="mt-1.5"
            disabled={selectedBlendIds.length < 2}
            onclick={viewBlend}
        >
            View blend
        </Button>
    </RegistrationThumbs>
</div>

<style>
    .tile {
        margin-top: 0.5em;
        padding: 0.4em 0.45em 0.45em;
        border: 1px solid rgba(255, 255, 255, 0.18);
        background: rgba(255, 255, 255, 0.07);
    }
    .tile:first-child {
        margin-top: 0;
    }
    .tile :global(.role:first-child) {
        margin-top: 0;
    }
    .role {
        margin-top: 0.45em;
    }
    .role-label {
        font-size: 0.75em;
        opacity: 0.8;
        margin-bottom: 0.25em;
    }
    ul.existing {
        list-style: none;
        margin: 0.25em 0 0.4em;
        padding: 0;
    }
</style>
