<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/types";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext, onMount } from "svelte";
    import type { FormAnnotationGET, FormSchemaGET } from "../../../types/openapi_types";
    import FormItem from "./FormItem.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { user: creator, formShortcut } = globalContext;

    const {
        image: { instance },
    } = viewerContext;

    const taskContext = getContext<TaskContext>("taskContext");

    //TODO: this should be part of the config?
    const exclude = new Set([
        "ETDRS-grid coordinates",
        "Pointset registration",
        "Affine registration",
        "RegistrationSet",
    ]);
    
    onMount(async () => {
        await globalContext.ensureFormSchemasLoaded();
    });

    // const allSchemas = formSchemas.filter(
    //     (schema) => !exclude.has(schema.name),
    // );
    let selectedSchema: FormSchemaGET | undefined = $state();

    const filters = [
        (annotation: FormAnnotationGET) => annotation.patient === instance.patient, //same patient
        (annotation: FormAnnotationGET) =>
            annotation.instance?.laterality == instance.laterality, // same eye
        (annotation: FormAnnotationGET) => annotation.study == instance.study, // same study
        (annotation: FormAnnotationGET) =>
            !exclude.has(annotation.formSchema.name),
    ];

    // TODO: refactor this, to be used as extension?
    if (taskContext) {
        const TaskDefinitionName = taskContext.task.definition.name;
        if (TaskDefinitionName === "Naevi") {
            selectedSchema = globalContext.formSchemas.all.find(
                (schema) => schema.name === "Naevi grading",
            );
        } else if (TaskDefinitionName === "ETDRS-grid placement") {
            selectedSchema = globalContext.formSchemas.all.find(
                (schema) => schema.name === "ETDRS-grid coordinates",
            );
            filters.push(
                (annotation: FormAnnotationGET) => annotation.instance == instance,
            );
        } else if (TaskDefinitionName === "Glaucoma grading") {
            selectedSchema = globalContext.formSchemas.all.find(
                (schema) => schema.name === "Glaucoma grading",
            );
        }
    }

    const forms = viewerContext.formAnnotations
        .filter((annotation) => filters.every((filter) => filter(annotation)))
        .filter(globalContext.segmentationsFilter)
        .sort((a, b) => a.id - b.id);

    function addForm() {
        if (!selectedSchema) return;
        FormAnnotation.createFrom(
            creator,
            instance,
            selectedSchema,
            taskContext?.subTask,
        );
    }

    let formShortcutSchema = $derived(
        globalContext.formSchemas.all.find((schema) => schema.name === formShortcut),
    );
    function addShortcut() {
        FormAnnotation.createFrom(
            creator,
            instance,
            formShortcutSchema!,
            taskContext?.subTask,
        );
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
        {#each viewerContext.formAnnotations as form, i (i)}
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
