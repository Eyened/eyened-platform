<script lang="ts">
    import {
        formAnnotations,
        formSchemas,
        formSchemasByName,
        createFormAnnotation,
    } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import type {
        FormAnnotationGET,
        FormSchemaGET,
    } from "../../../types/openapi_types";
    import { HIDE_FROM_FORM_PANEL_NAMES } from "$lib/config/builtinFormSchemas";
    import FormItem from "./FormItem.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { formShortcut } = globalContext;

    const {
        image: { instance },
    } = viewerContext;

    const taskContext = getContext<TaskContext>("taskContext");

    let selectedSchema: FormSchemaGET | undefined = $state();

    const filters = [
        (annotation: FormAnnotationGET) => {
            const schema = formSchemas.get(annotation.form_schema_id);
            return !schema || !HIDE_FROM_FORM_PANEL_NAMES.has(schema.name);
        },
        (annotation: FormAnnotationGET) =>
            annotation.patient_id === instance.patient.id, //same patient
        (annotation: FormAnnotationGET) => {
            const schema = formSchemas.get(annotation.form_schema_id);
            if (!schema) return false;
            if (schema.entity_type == "StudyEye") {
                return (
                    annotation.study_id == instance.study?.id &&
                    annotation.laterality == instance.laterality
                );
            }

            //TODO: check for other entity types
            return annotation.image_id == instance.id;
        },
    ];

    const taskConfig = taskContext?.task.task_definition.config;
    if (taskConfig?.form_schema_name) {
        const schema = formSchemasByName.get(taskConfig.form_schema_name);
        if (schema && !HIDE_FROM_FORM_PANEL_NAMES.has(schema.name)) {
            selectedSchema = schema;
        }
    }
    if (taskConfig?.form_image_scope) {
        filters.push(
            (annotation: FormAnnotationGET) =>
                annotation.image_id == instance.id,
        );
    }

    const forms = $derived(
        formAnnotations
            .filter((annotation) =>
                filters.every((filter) => filter(annotation)),
            )
            .sort((a, b) => a.id - b.id),
    );

    const selectableSchemas = $derived(
        [...formSchemas.values()].filter(
            (schema) => !HIDE_FROM_FORM_PANEL_NAMES.has(schema.name),
        ),
    );

    const formShortcutSchema = $derived.by(() => {
        if (!formShortcut || HIDE_FROM_FORM_PANEL_NAMES.has(formShortcut))
            return undefined;
        return formSchemasByName.get(formShortcut);
    });

    async function addFormWithSchema(schema: FormSchemaGET | undefined) {
        if (!schema) return;
        await createFormAnnotation({
            form_schema_id: schema.id,
            patient_id: instance.patient.id,
            study_id: instance.study?.id ?? undefined,
            image_id: instance.id,
            laterality: instance.laterality ?? undefined,
            sub_task_id: taskContext?.subTask?.id,
            form_data: {},
        });
    }
</script>

<div class="main">
    <div class="new-form">
        <div>
            <select class="schema-select" bind:value={selectedSchema}>
                <option value={undefined} disabled
                    >-- select form type --</option
                >
                {#each selectableSchemas as schema}
                    <option value={schema}>{schema.name}</option>
                {/each}
            </select>
        </div>

        <div>
            <button
                onclick={() => addFormWithSchema(selectedSchema)}
                disabled={!selectedSchema}
            >
                Create new form
            </button>
        </div>

        {#if formShortcutSchema}
            <div>
                <button onclick={() => addFormWithSchema(formShortcutSchema)}>
                    Create {formShortcut}
                </button>
            </div>
        {/if}
    </div>
    <div>
        {#each forms as form (form.id)}
            <FormItem {form} />
        {/each}
    </div>
</div>

<style>
    .main {
        display: flex;
        flex-direction: column;
        padding: 0.5em;
        flex: 1;
    }
    div.new-form {
        display: flex;
        flex-direction: column;
        padding: 0.5em;
    }
    button {
        margin-top: 0.5em;
    }
    button {
        color: rgba(255, 255, 255, 0.8);
        padding: 0.2em;
        border: 1px solid rgba(255, 255, 255, 0.1);
        background-color: rgba(255, 255, 255, 0.2);
        border-radius: 2px;
    }
    button:disabled {
        cursor: not-allowed;
        opacity: 0.3;
    }
    button:not(:disabled):hover {
        cursor: pointer;
        background-color: rgba(255, 255, 255, 0.3);
    }
    select.schema-select {
        /* Inherited sidebar text color breaks native <select> on Windows */
        color: rgba(255, 255, 255, 0.8);
        background-color: rgba(255, 255, 255, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 2px;
        padding: 0.2em;
        color-scheme: dark;
    }
    select.schema-select option {
        color: rgba(255, 255, 255, 0.9);
        background-color: rgb(30, 30, 30);
    }
</style>
