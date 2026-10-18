<script lang="ts">
    import {
        createFormAnnotation,
        formAnnotations,
        instances,
    } from "$lib/data";
    import { getThumbUrl } from "$lib/data-loading/utils";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import { getContext } from "svelte";
    import type { FormSchemaGET, ImageGET } from "../../../types/openapi_types";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import {
        annotationMatchesEye,
        canOpenRegistration,
        groupOpenImages,
        orderByInstanceIds,
        type EyeGroup,
        type EyeLaterality,
        type OpenImage,
    } from "./groupOpenImages";

    interface Props {
        active: boolean;
        registrationSchema: FormSchemaGET;
    }
    const { active, registrationSchema }: Props = $props();
    // `active` stays in the panel contract. Read it in an effect so Svelte
    // does not treat the prop as captured once at init.
    $effect(() => {
        void active;
    });

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );
    const taskContext = getContext<TaskContext | undefined>("taskContext");
    const globalContext = getContext<GlobalContext>("globalContext");

    const openImages = $derived.by(() => {
        const images: OpenImage[] = [];
        for (const image of viewerWindowContext.topViewers.keys()) {
            // Skip only real volumes and slice stacks. Missing is2D stays.
            if (image.is2D === false) continue;
            images.push({
                imageId: image.image_id,
                instanceId: image.instance.id,
                patientId: image.instance.patient.id,
                laterality: image.instance.laterality ?? null,
                studyId: image.instance.study?.id,
            });
        }
        return orderByInstanceIds(
            images,
            viewerWindowContext.instanceIds ?? [],
        );
    });

    const groups = $derived(groupOpenImages(openImages));

    let groupUi = $state<
        Record<string, { fixedId: string; movingId: string; choice: string }>
    >({});

    let openingGroups = $state(new Set<string>());

    function markCreateInFlight(key: string) {
        const next = new Set(openingGroups);
        next.add(key);
        openingGroups = next;
    }

    function clearCreateInFlight(key: string) {
        const next = new Set(openingGroups);
        next.delete(key);
        openingGroups = next;
    }

    function groupKey(patientId: number, laterality: EyeLaterality): string {
        return `${patientId}:${laterality ?? "unset"}`;
    }

    function selectionFor(key: string) {
        return groupUi[key] ?? { fixedId: "", movingId: "", choice: "" };
    }

    function setFixed(key: string, imageId: string) {
        const current = selectionFor(key);
        groupUi[key] = {
            fixedId: imageId,
            movingId: current.movingId === imageId ? "" : current.movingId,
            choice: current.choice,
        };
    }

    function setMoving(key: string, imageId: string) {
        const current = selectionFor(key);
        groupUi[key] = {
            fixedId: current.fixedId === imageId ? "" : current.fixedId,
            movingId: imageId,
            choice: current.choice,
        };
    }

    function setChoice(key: string, choice: string) {
        const current = selectionFor(key);
        groupUi[key] = { ...current, choice };
    }

    function annotationsFor(group: EyeGroup) {
        return formAnnotations.filter(
            (annotation) =>
                annotationMatchesEye(
                    annotation,
                    registrationSchema.id,
                    group.patientId,
                    group.laterality,
                    (imageId) => instances.get(imageId)?.laterality ?? null,
                ) && globalContext.canEdit(annotation),
        );
    }

    function imageInGroup(
        group: EyeGroup,
        imageId: string,
    ): OpenImage | undefined {
        return group.images.find((image) => image.imageId === imageId);
    }

    async function openGroup(group: EyeGroup) {
        const key = groupKey(group.patientId, group.laterality);
        const { fixedId, movingId, choice } = selectionFor(key);
        if (!canOpenRegistration(fixedId, movingId, choice || null)) return;
        const fixed = imageInGroup(group, fixedId);
        const moving = imageInGroup(group, movingId);
        if (!fixed || !moving) return;

        let annotationId: number;
        if (choice === "new") {
            if (openingGroups.has(key)) return;
            markCreateInFlight(key);
            try {
                const created = await createFormAnnotation({
                    form_schema_id: registrationSchema.id,
                    patient_id: group.patientId,
                    image_id: fixed.instanceId,
                    study_id: fixed.studyId,
                    sub_task_id: taskContext?.subTask?.id,
                    form_data: {},
                    ...(group.laterality != null
                        ? { laterality: group.laterality }
                        : {}),
                });
                annotationId = created.id;
            } catch {
                return;
            } finally {
                clearCreateInFlight(key);
            }
        } else {
            annotationId = Number(choice);
        }

        viewerWindowContext.openRegistrationEditor({
            imageIds: [fixed.imageId, moving.imageId],
            annotationId,
        });
    }
</script>

<div class="main">
    {#each groups as group (groupKey(group.patientId, group.laterality))}
        {@const key = groupKey(group.patientId, group.laterality)}
        {@const selection = selectionFor(key)}
        <fieldset>
            <legend>
                Patient {group.patientId}
                {group.laterality ?? "unset"}
            </legend>
            <div class="role">
                <div class="role-label">Fixed</div>
                <div class="thumbs">
                    {#each group.images as image (image.imageId)}
                        <button
                            type="button"
                            class="thumb"
                            class:selected={selection.fixedId === image.imageId}
                            title={image.instanceId}
                            aria-label="Fixed {image.instanceId}"
                            onclick={() => setFixed(key, image.imageId)}
                        >
                            <img
                                src={getThumbUrl(
                                    { id: image.instanceId } as ImageGET,
                                    144,
                                )}
                                alt=""
                                draggable="false"
                            />
                        </button>
                    {/each}
                </div>
            </div>
            <div class="role">
                <div class="role-label">Moving</div>
                <div class="thumbs">
                    {#each group.images as image (image.imageId)}
                        <button
                            type="button"
                            class="thumb"
                            class:selected={selection.movingId ===
                                image.imageId}
                            title={image.instanceId}
                            aria-label="Moving {image.instanceId}"
                            onclick={() => setMoving(key, image.imageId)}
                        >
                            <img
                                src={getThumbUrl(
                                    { id: image.instanceId } as ImageGET,
                                    144,
                                )}
                                alt=""
                                draggable="false"
                            />
                        </button>
                    {/each}
                </div>
            </div>
            <select
                value={selection.choice}
                onchange={(event) => setChoice(key, event.currentTarget.value)}
            >
                <option value=""></option>
                <option value="new">New</option>
                {#each annotationsFor(group) as annotation (annotation.id)}
                    <option value={String(annotation.id)}>
                        {annotation.creator.name} [{annotation.id}]
                    </option>
                {/each}
            </select>
            <button
                type="button"
                disabled={!canOpenRegistration(
                    selection.fixedId,
                    selection.movingId,
                    selection.choice || null,
                ) || openingGroups.has(key)}
                onclick={() => openGroup(group)}
            >
                Open
            </button>
        </fieldset>
    {/each}
</div>

<style>
    div.main {
        padding: 0.5em;
        min-height: 0;
        flex: 1 1 auto;
        overflow-y: auto;
    }
    fieldset {
        margin: 0 0 0.5em;
        padding: 0.4em;
        border: 1px solid rgba(255, 255, 255, 0.25);
    }
    .role {
        margin-top: 0.45em;
    }
    .role-label {
        font-size: 0.75em;
        opacity: 0.8;
        margin-bottom: 0.25em;
    }
    .thumbs {
        display: flex;
        flex-direction: row;
        gap: 0.35em;
        overflow-x: auto;
    }
    button.thumb {
        flex: 0 0 auto;
        padding: 0;
        border: 2px solid transparent;
        background: black;
        cursor: pointer;
        line-height: 0;
    }
    button.thumb.selected {
        border-color: white;
    }
    button.thumb img {
        width: 3.2rem;
        height: 3.2rem;
        object-fit: contain;
        display: block;
    }
    select,
    button {
        margin-top: 0.4em;
    }
</style>
