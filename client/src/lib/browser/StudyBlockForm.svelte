<script lang="ts">
    import type { Study } from "$lib/datamodel/study";
    import type { Instance } from "$lib/datamodel/instance";

    import { data } from "$lib/datamodel/model";
    import FormItem from "$lib/viewer-window/panelForm/FormItem.svelte";
    import type { FormAnnotation } from "$lib/datamodel/formAnnotation";
    import { globalContext } from "$lib/main";
    import { getContext } from "svelte";
    import type { TaskContext } from "$lib/types";

    interface Props {
        title: string;
        schema_name: string;
        split_laterality: boolean;
        study: Study;
        create_new: boolean;
    }
    let { title, split_laterality, study, schema_name, create_new }: Props =
        $props();

    const { creator } = globalContext;
    const taskContext = getContext<TaskContext | undefined>("taskContext");

    const { formAnnotations, formSchemas } = data;
    const formSchema = formSchemas.find(
        (schema) => schema.name === schema_name,
    );
    if (!formSchema) {
        console.error(`Form schema ${schema_name} not found`);
    }
    const left_instance = study.instances
        .filter((instance) => instance.laterality === "L")
        .first();
    const right_instance = study.instances
        .filter((instance) => instance.laterality === "R")
        .first();
    const first_instance = study.instances.first();

    const filters = [
        (annotation: FormAnnotation) => annotation.study === study,
        (annotation: FormAnnotation) => annotation.formSchema === formSchema,
    ];
    const forms = formAnnotations
        .filter((annotation) => filters.every((filter) => filter(annotation)))
        .sort((a, b) => a.id - b.id);

    const left = forms.filter((form) => form.instance?.laterality === "L");
    const right = forms.filter((form) => form.instance?.laterality === "R");

    async function add(instance: Instance) {
        const item: any = {
            formSchema,
            patient: instance.patient,
            study: instance.study,
            instance,
            creator,
        };
        if (taskContext) {
            item.subTask = taskContext.subTask;
        }
        formAnnotations.create(item);
    }
</script>

{#snippet form_item(
    instance: Instance | undefined,
    forms: FormAnnotation[],
    post_fix: string = "",
)}
    {#if instance && create_new}
        <div>
            <button onclick={() => add(instance)}>
                Create {schema_name}
                {post_fix}
            </button>
        </div>
    {/if}

    {#each forms as form}
        <div>
            <div class="form-item">
                <FormItem {form} theme="light" />
            </div>
        </div>
    {/each}
{/snippet}

<div id="main">
    <h4>{title}</h4>
    {#if split_laterality}
        <div id="eyes">
            <div>
                {@render form_item(right_instance, $right, "OD")}
            </div>
            <div>
                {@render form_item(left_instance, $left, "OS")}
            </div>
        </div>
    {:else}
        {@render form_item(first_instance, $forms)}
    {/if}
</div>

<style>
    div {
        display: flex;
    }
    h4 {
        padding: 0;
        margin: 0;
        margin-top: 0.5em;
        margin-bottom: 0.5em;
    }
    div#main {
        flex-direction: column;
        padding-left: 0.5em;
        padding-right: 0.5em;
    }
    div#eyes {
        flex-direction: row;
    }
    div#eyes > div {
        flex-direction: column;
        flex: 1;
    }
    div.form-item {
        flex-direction: column;
        width: 20em;
    }
</style>
