<script lang="ts">
    import {
        createFormAnnotation,
        formAnnotations,
        formSchemasByName,
    } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { resolveRefs, type JSONSchema } from "$lib/forms/schemaType";
    import { SchemaValidator } from "$lib/forms/schemaValidator.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import { CLIENT_DEFAULTS, mergeClientConfig } from "../taskConfigLayout";
    import { findFormAnnotation } from "../panelForm/findFormAnnotation";
    import {
        buildFormAnnotationCreatePayload,
        resolveFormEntityScope,
    } from "../panelForm/formEntityScope";
    import { openFormInNewWindow } from "../panelForm/openFormInNewWindow";

    interface Props {
        title?: string;
        active?: boolean;
    }
    let { title: _title = "Grading" }: Props = $props();

    const globalContext = getContext<GlobalContext>("globalContext");
    const taskContext = getContext<TaskContext>("taskContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");

    const taskConfig = mergeClientConfig(
        CLIENT_DEFAULTS,
        taskContext?.task.task_definition.config,
    );
    const instance = viewerContext.image.instance;

    const schema = $derived.by(() => {
        const name = taskConfig?.form_schema_name;
        if (!name) return undefined;
        return formSchemasByName.get(name);
    });

    const formContext = $derived({
        patientId: instance.patient.id,
        studyId: instance.study?.id,
        imageId: instance.id,
        laterality: instance.laterality ?? undefined,
    });

    const entityScope = $derived.by(() =>
        resolveFormEntityScope(schema?.entity_type),
    );

    const annotation = $derived.by(() => {
        if (!schema) return undefined;
        return findFormAnnotation({
            annotations: Array.from(formAnnotations.values()),
            schemaId: schema.id,
            userId: globalContext.user.id,
            ctx: formContext,
            subTaskId: taskContext?.subTask?.id,
            schemaEntityType: schema.entity_type,
        });
    });

    const validator = $derived.by(() => {
        if (!schema || !annotation) return undefined;
        const resolved = resolveRefs(schema.schema as JSONSchema);
        return new SchemaValidator(resolved, annotation.form_data ?? {});
    });

    const statusLabel = $derived.by(() => {
        if (!annotation) return "Not graded";
        if (!validator) return "—";
        if (validator.isValid) return "Valid ✓";
        return `Incomplete (${validator.errors.length})`;
    });

    const buttonLabel = $derived(annotation ? "Open grading" : "Grade");
    const canEdit = $derived(
        annotation ? globalContext.canEdit(annotation) : true,
    );
    const gradeDisabled = $derived(!schema);
    let submitting = $state(false);

    async function onGradeClick() {
        if (!schema || submitting) return;

        submitting = true;
        try {
            let form = annotation;
            if (!form) {
                form = await createFormAnnotation(
                    buildFormAnnotationCreatePayload({
                        formSchemaId: schema.id,
                        scope: entityScope,
                        ctx: formContext,
                        subTaskId: taskContext?.subTask?.id,
                    }),
                );
            }

            openFormInNewWindow(form, canEdit, viewerContext);
        } finally {
            submitting = false;
        }
    }
</script>

<div class="main">
    {#if !schema}
        <p class="warning">Form schema not configured or not found.</p>
    {:else}
        <p class="schema">Schema: {schema.name}</p>
        <p class="scope">Scope: {entityScope}</p>
        <p class="status {statusLabel.toLowerCase()}">Status: {statusLabel}</p>
    {/if}

    <button onclick={onGradeClick} disabled={gradeDisabled || submitting}>
        {buttonLabel}
    </button>
</div>

<style>
    .main {
        display: flex;
        flex-direction: column;
        padding: 0.5em;
        flex: 1;
        gap: 0.4em;
    }
    .warning {
        color: #f87171;
        font-size: 0.85em;
    }
    .schema,
    .scope,
    .status {
        font-size: 0.85em;
        margin: 0;
    }
    .status.valid {
        color: #16a34a;
    }
    .status.incomplete {
        color: #f87171;
    }
    .status.invalid {
        color: #f87171;
    }
    button {
        color: rgba(255, 255, 255, 0.8);
        padding: 0.2em;
        border: 1px solid rgba(255, 255, 255, 0.1);
        background-color: rgba(255, 255, 255, 0.2);
        border-radius: 2px;
        margin-top: 0.25em;
    }
    button:disabled {
        cursor: not-allowed;
        opacity: 0.3;
    }
    button:not(:disabled):hover {
        cursor: pointer;
        background-color: rgba(255, 255, 255, 0.3);
    }
</style>
