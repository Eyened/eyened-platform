<script lang="ts">
    import { formAnnotations, formSchemas, formSchemasByName, createFormAnnotation, instances } from "$lib/data";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from '$lib/tasks/TaskContext.svelte';
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import type { FormAnnotationGET, FormSchemaGET } from "../../../types/openapi_types";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import FormItem from "./FormItem.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const viewerWindowContext = getContext<ViewerWindowContext>("viewerWindowContext");
    const { formShortcut } = globalContext;

    const {
        image: { instance },
    } = viewerContext;

    const taskContext = getContext<TaskContext>("taskContext");

    //TODO: this should be part of the config?
    const form_schema_ids_to_exclude = new Set([
        2, 6, 8, 9
    ]);
    
    
    let selectedSchema: FormSchemaGET | undefined = $state();

    const filters = [
        (annotation: FormAnnotationGET) => !form_schema_ids_to_exclude.has(annotation.form_schema_id),    
        (annotation: FormAnnotationGET) => annotation.patient_id === instance.patient.id, //same patient
        (annotation: FormAnnotationGET) => {
            const schema = formSchemas.get(annotation.form_schema_id);
            if (!schema) return false;
            if (schema.entity_type == 'StudyEye') {
                return annotation.study_id == instance.study?.id && annotation.laterality == instance.laterality;
            }

            //TODO: check for other entity types
            return annotation.image_id == instance.id;     
        }
        
    ];
    

    // TODO: refactor this, to be used as extension?
    if (taskContext) {
        const TaskDefinitionName = taskContext.task.task_definition.name;
        if (TaskDefinitionName === "Naevi") {
            selectedSchema = formSchemasByName.get("Naevi grading");
        } else if (TaskDefinitionName === "ETDRS-grid placement") {
            selectedSchema = formSchemasByName.get("ETDRS-grid coordinates");
            filters.push(
                (annotation: FormAnnotationGET) => annotation.image_id == instance.id,
            );
        } else if (TaskDefinitionName === "Glaucoma grading") {
            selectedSchema = formSchemasByName.get("Glaucoma grading");
        }
    }


    const forms = $derived(
        formAnnotations.filter((annotation) => filters.every((filter) => filter(annotation)))        
        .sort((a, b) => a.id - b.id)
    )

    const formShortcutSchema = $derived(
        formShortcut ? formSchemasByName.get(formShortcut) : undefined
    );

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
            <select bind:value={selectedSchema}>
                <option value={undefined} disabled>-- select form type --</option>
                {#each formSchemas.values() as schema}
                    <option value={schema}>{schema.name}</option>
                {/each}
            </select>
        </div>

        <div>
            <button onclick={() => addFormWithSchema(selectedSchema)} disabled={!selectedSchema}>
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
</style>
