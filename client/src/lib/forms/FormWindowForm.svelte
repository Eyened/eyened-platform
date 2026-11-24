<!--
@component
The form in the window: a header naming its target, its save state and whose it is; a bar with tags and Vertical; then the form.
-->
<script lang="ts">
    import { browser } from "$app/environment";
    import { Checkbox } from "$lib/components/ui/checkbox/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import {
        formSchemas,
        instances,
        patients,
        studies,
        tagFormAnnotation,
        untagFormAnnotation,
    } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { updateTagFormAnnotation } from "$lib/data/helpers";
    import { getDefault, type JSONSchema } from "$lib/forms/schemaType";
    import SchemaForm from "$lib/forms/SchemaForm.svelte";
    import SyncStatus from "$lib/layers/SyncStatus.svelte";
    import { formAnnotationSaver } from "$lib/saving/formAnnotationSavers";
    import Tagger from "$lib/tags/Tagger.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import { resolveFormEntityScope } from "$lib/viewer-window/panelForm/formEntityScope";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import {
        deviceText,
        eyeLabel,
        modalityField,
    } from "$lib/workspace/imageMeta";
    import { getContext, onMount, setContext } from "svelte";
    import type { FormAnnotationGET } from "../../types/openapi_types";
    import { READY_ATTEMPTED } from "./formContext";
    import { ABOUT, schemaName, windowHeading } from "./formTargets";

    let {
        form,
        canEdit,
        viewerContext,
    }: {
        form: FormAnnotationGET;
        canEdit: boolean;
        viewerContext?: ViewerContext;
    } = $props();
    const uid = $props.id();

    if (viewerContext) setContext("viewerContext", viewerContext);
    setContext("pointFormAnnotationId", form.id);
    if (form.image_id) setContext("pointBoundImageId", form.image_id);

    const taskContext = getContext<TaskContext | undefined>("taskContext");
    const readyAttempted = getContext<(() => boolean) | undefined>(
        READY_ATTEMPTED,
    );
    const userId = getContext<GlobalContext | undefined>("globalContext")?.user
        .id;

    const formSchema = $derived(formSchemas.get(form.form_schema_id)!);
    const schema = $derived(formSchema.schema as JSONSchema);
    const scope = $derived(resolveFormEntityScope(formSchema.entity_type));
    const meta = $derived(
        form.image_id ? instances.get(form.image_id) : undefined,
    );

    const topLine = $derived(
        [
            taskContext
                ? `Set ${taskContext.subTaskIndex + 1} of ${taskContext.task.num_tasks}`
                : null,
            schemaName(formSchema),
        ]
            .filter(Boolean)
            .join(" · "),
    );
    const heading = $derived(
        windowHeading(scope, {
            patient:
                meta?.patient.identifier ??
                patients.get(form.patient_id)?.identifier ??
                `Patient ${form.patient_id}`,
            eye: eyeLabel(form.laterality ?? meta?.laterality ?? null),
            modality: meta ? modalityField(meta) : null,
            date:
                meta?.study.date ??
                (form.study_id != null
                    ? studies.get(form.study_id)?.date
                    : undefined) ??
                null,
        }),
    );
    const about = $derived(
        [meta ? deviceText(meta) : "", ABOUT[scope]]
            .filter(Boolean)
            .join(" · "),
    );
    const metaLine = $derived(
        [
            `#${form.id}`,
            form.creator?.id === userId
                ? "yours"
                : `${form.creator?.name}'s form`,
            form.form_annotation_reference_id
                ? `copy of #${form.form_annotation_reference_id}`
                : null,
        ]
            .filter(Boolean)
            .join(" · "),
    );

    // Keep value as independent $state (not derived from form.form_data), so a store update
    // from the saved reply doesn't loop back into the form. It starts from the form once, on mount.
    let value: unknown = $state(undefined);
    let loaded = $state(false);
    // One saver per annotation on the page; it outlives this window.
    let root: HTMLElement | null = $state(null);
    const saver = formAnnotationSaver(form.id, "form", {
        to: "focus",
        focus: () => root?.ownerDocument.defaultView?.focus(),
    });

    onMount(() => {
        value = form.form_data || getDefault(schema);
        loaded = true;
    });

    function onchange(next: unknown) {
        if (!canEdit) return;
        // Always apply `next`, including undefined/null/''/0/false. Callers use
        // undefined to omit/clear (PointField Remove, bare-single Clear, SchemaForm trash).
        value = next;
        // JSON body cannot be undefined — persist null for an omitted root value.
        saver.edit(next ?? null);
    }

    function readLocalStorageBoolean(key: string, defaultValue: boolean) {
        const stored = browser ? localStorage.getItem(key) : null;
        return stored === null ? defaultValue : stored === "true";
    }
    let vertical = $state(
        readLocalStorageBoolean("form-item-content-vertical", true),
    );
    $effect(() => {
        localStorage.setItem("form-item-content-vertical", vertical.toString());
    });
</script>

<Tooltip.Provider>
    <header class="flex flex-col gap-1 px-4 pt-4 pb-2" bind:this={root}>
        <p class="text-label-01 text-text-secondary">{topLine}</p>
        <div class="flex items-start gap-4">
            <h1
                tabindex="-1"
                class="min-w-0 flex-1 text-heading-03 text-text-primary"
            >
                {heading}
            </h1>
            <!-- Carbon icon indicators with their words; this window has no header to announce them, so it is the live region. -->
            <div role="status" class="shrink-0">
                <SyncStatus
                    sync={saver.state}
                    onretry={() => void saver.flush()}
                />
            </div>
        </div>
        {#if about}
            <p class="text-body-compact-01 text-text-secondary">{about}</p>
        {/if}
        <p class="flex items-center gap-2 text-label-01 text-text-secondary">
            {#if !canEdit}<Tag>Read-only</Tag>{/if}{metaLine}
        </p>
    </header>
    <div
        class="flex flex-wrap items-center gap-4 border-b border-border-subtle-01 px-4 pb-2"
    >
        <Tagger
            tagType="FormAnnotation"
            tags={form.tags ?? []}
            tag={(id) => tagFormAnnotation(form, id)}
            untag={(id) => untagFormAnnotation(form, id)}
            onUpdate={(tagId, comment) =>
                updateTagFormAnnotation(form.id, tagId, comment)}
        />
        <!-- Carbon checkbox labels are body-compact-01 in text-primary, not the field label's 12 px grey. -->
        <Field.Field orientation="horizontal" class="w-auto">
            <Checkbox id="{uid}-vertical" bind:checked={vertical} />
            <Field.Label
                for="{uid}-vertical"
                class="text-body-compact-01 text-text-primary"
                >Vertical</Field.Label
            >
        </Field.Field>
    </div>
    <div class="flex flex-1 flex-col overflow-auto p-4">
        {#if loaded}
            <SchemaForm
                {schema}
                {value}
                {onchange}
                {canEdit}
                {vertical}
                markReadyAttempted={readyAttempted?.() ?? false}
            />
        {/if}
    </div>
</Tooltip.Provider>
