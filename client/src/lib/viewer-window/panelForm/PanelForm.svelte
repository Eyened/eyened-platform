<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from '$lib/tasks/TaskContext.svelte';
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext, onMount } from "svelte";
    import type { FormAnnotationGET, FormSchemaGET } from "../../../types/openapi_types";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import FormItem from "./FormItem.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const viewerWindowContext = getContext<ViewerWindowContext>("viewerWindowContext");
    const formAnnotationRepo = viewerWindowContext.formAnnotationsRepo;
    const { user: creator, formShortcut } = globalContext;

    const {
        image: { instance },
    } = viewerContext;

    const taskContext = getContext<TaskContext>("taskContext");

    //TODO: this should be part of the config?
    const form_schama_ids_to_exclude = new Set([
        2, 6, 8, 9
    ]);
    
    onMount(async () => {
        await globalContext.ensureFormSchemasLoaded();
    });

    let selectedSchema: FormSchemaGET | undefined = $state();

    const filters = [
        (annotation: FormAnnotationGET) => annotation.patient_id === instance.patient.id, //same patient
        (annotation: FormAnnotationGET) =>
            annotation.image_instance_id == instance.id, // same eye/laterality via instance
        (annotation: FormAnnotationGET) => annotation.study_id == instance.study?.id, // same study
        (annotation: FormAnnotationGET) => !form_schama_ids_to_exclude.has(annotation.form_schema_id)
    ];

    // TODO: refactor this, to be used as extension?
    if (taskContext) {
        const TaskDefinitionName = taskContext.task.task_definition.name;
        if (TaskDefinitionName === "Naevi") {
            selectedSchema = globalContext.formSchemas.all.find(
                (schema) => schema.name === "Naevi grading",
            );
        } else if (TaskDefinitionName === "ETDRS-grid placement") {
            selectedSchema = globalContext.formSchemas.all.find(
                (schema) => schema.name === "ETDRS-grid coordinates",
            );
            filters.push(
                (annotation: FormAnnotationGET) => annotation.image_instance_id == instance.id,
            );
        } else if (TaskDefinitionName === "Glaucoma grading") {
            selectedSchema = globalContext.formSchemas.all.find(
                (schema) => schema.name === "Glaucoma grading",
            );
        }
    }


    const forms = $derived(
        formAnnotationRepo.all
        .filter((annotation) => filters.every((filter) => filter(annotation)))
        .filter(globalContext.segmentationsFilter)
        .sort((a, b) => a.id - b.id)
    )


    // Convert GET rows to objects
    const formObjects = $derived(
        forms.map(a => formAnnotationRepo.object(a.id))
    );

    async function addForm() {
        if (!selectedSchema) return;
        await formAnnotationRepo.create({
            form_schema_id: selectedSchema.id,
            patient_id: instance.patient.id,
            study_id: instance.study?.id ?? undefined,
            image_instance_id: instance.id,
            sub_task_id: taskContext?.subTask?.id,
            form_data: {},
        });
    }

    let formShortcutSchema = $derived(
        globalContext.formSchemas.all.find((schema) => schema.name === formShortcut),
    );
    async function addShortcut() {
        if (!formShortcutSchema) return;
        await formAnnotationRepo.create({
            form_schema_id: formShortcutSchema.id,
            patient_id: instance.patient.id,
            study_id: instance.study?.id ?? undefined,
            image_instance_id: instance.id,
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
                {#each globalContext.formSchemas.all as schema}
                    <option value={schema}>{schema.name}</option>
                {/each}
            </select>
        </div>

        <div>
            <button onclick={addForm} disabled={!selectedSchema}>
                Create new form
            </button>
        </div>

        {#if formShortcutSchema}
            <div>
                <button onclick={addShortcut}> Create {formShortcut} </button>
            </div>
        {/if}
    </div>
    <div>
        {#each formObjects as form, i (i)}
            <FormItem {form} {formAnnotationRepo} />
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
