<script lang="ts">
    import {
        createFormAnnotation,
        formAnnotations,
        instances,
    } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import { getContext } from "svelte";
    import type { FormSchemaGET } from "../../../types/openapi_types";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import {
        annotationMatchesEye,
        canOpenRegistration,
        groupOpenImages,
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
    void globalContext;

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
        return images;
    });

    const groups = $derived(groupOpenImages(openImages));

    let groupUi = $state<Record<string, { checked: string[]; choice: string }>>(
        {},
    );

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

    function checkedFor(key: string): string[] {
        return groupUi[key]?.checked ?? [];
    }

    function choiceFor(key: string): string {
        return groupUi[key]?.choice ?? "";
    }

    function toggleImage(key: string, imageId: string) {
        const current = checkedFor(key);
        const checked = current.includes(imageId)
            ? current.filter((id) => id !== imageId)
            : [...current, imageId];
        groupUi[key] = { checked, choice: choiceFor(key) };
    }

    function setChoice(key: string, choice: string) {
        groupUi[key] = { checked: checkedFor(key), choice };
    }

    function annotationsFor(group: EyeGroup) {
        return formAnnotations.filter((annotation) =>
            annotationMatchesEye(
                annotation,
                registrationSchema.id,
                group.patientId,
                group.laterality,
                (imageId) => instances.get(imageId)?.laterality ?? null,
            ),
        );
    }

    function checkedInGroupOrder(group: EyeGroup, key: string): OpenImage[] {
        const checked = new Set(checkedFor(key));
        return group.images.filter((image) => checked.has(image.imageId));
    }

    async function openGroup(group: EyeGroup) {
        const key = groupKey(group.patientId, group.laterality);
        const choice = choiceFor(key);
        const ordered = checkedInGroupOrder(group, key);
        if (!canOpenRegistration(ordered.length, choice || null)) return;

        let annotationId: number;
        if (choice === "new") {
            if (openingGroups.has(key)) return;
            const first = ordered[0];
            if (!first) return;
            markCreateInFlight(key);
            try {
                const created = await createFormAnnotation({
                    form_schema_id: registrationSchema.id,
                    patient_id: group.patientId,
                    image_id: first.instanceId,
                    study_id: first.studyId,
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
            imageIds: ordered.map((image) => image.imageId),
            annotationId,
        });
    }
</script>

<div class="main">
    {#each groups as group (groupKey(group.patientId, group.laterality))}
        {@const key = groupKey(group.patientId, group.laterality)}
        {@const checked = checkedFor(key)}
        {@const choice = choiceFor(key)}
        <fieldset>
            <legend>
                Patient {group.patientId}
                {group.laterality ?? "unset"}
            </legend>
            {#each group.images as image (image.imageId)}
                <label>
                    {image.imageId}<input
                        type="checkbox"
                        checked={checked.includes(image.imageId)}
                        onclick={(event) => {
                            event.preventDefault();
                            toggleImage(key, image.imageId);
                        }}
                    />
                </label>
            {/each}
            <select
                value={choice}
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
                disabled={!canOpenRegistration(checked.length, choice || null) ||
                    openingGroups.has(key)}
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
    label {
        display: flex;
        align-items: center;
        gap: 0.4em;
    }
    select,
    button {
        margin-top: 0.4em;
    }
</style>
