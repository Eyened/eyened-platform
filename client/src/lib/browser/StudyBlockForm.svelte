<script lang="ts">
    import type {
        FormAnnotationGET,
        FormSchemaGET,
        StudyGET,
    } from "../../types/openapi_types";
    import { createFormAnnotation } from "$lib/data/api";
    import { formAnnotations } from "$lib/data/stores.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import FormItem from "$lib/viewer-window/panelForm/FormItem.svelte";
    import { Button } from "$lib/components/ui/button";
    import Add from "carbon-icons-svelte/lib/Add.svelte";
    import { getContext } from "svelte";

    interface Props {
        title: string;
        formSchema: FormSchemaGET;
        split_laterality: boolean;
        study: StudyGET;
        create_new: boolean;
    }
    let {
        title,
        split_laterality = true,
        study,
        formSchema,
        create_new,
    }: Props = $props();

    const taskContext = getContext<TaskContext | undefined>("taskContext");

    const forms = $derived(
        formAnnotations
            .filter(
                (annotation) =>
                    annotation.study_id === study.id &&
                    annotation.form_schema_id === formSchema.id,
            )
            .sort((a, b) => a.id - b.id),
    );

    const leftForms = $derived(forms.filter((form) => form.laterality === "L"));

    const rightForms = $derived(
        forms.filter((form) => form.laterality === "R"),
    );

    async function create(laterality: "L" | "R" | undefined) {
        await createFormAnnotation({
            form_schema_id: formSchema.id,
            patient_id: study.patient.id,
            study_id: study.id,
            laterality: laterality,
            sub_task_id: taskContext?.subTask?.id,
            form_data: {},
        });
    }
</script>

{#snippet form_item(
    laterality: "L" | "R" | undefined,
    forms: FormAnnotationGET[],
    suffix: string = "",
)}
    {#if laterality !== undefined && create_new}
        <Button
            onclick={() => create(laterality)}
            variant="outline"
            size="sm"
            class="self-start"
        >
            Create {formSchema.name}
            {suffix}
            <Add aria-hidden="true" />
        </Button>
    {/if}

    {#each forms as form (form.id)}
        <div class="flex w-full max-w-80 flex-col">
            <FormItem {form} theme="light" />
        </div>
    {/each}
{/snippet}

<div class="flex flex-col gap-2 pt-4">
    <h3 class="text-heading-compact-01">{title}</h3>
    {#if split_laterality}
        <div class="flex gap-4 max-md:flex-col">
            <div class="flex flex-1 flex-col gap-2">
                {@render form_item("R", rightForms, "OD")}
            </div>
            <div class="flex flex-1 flex-col gap-2">
                {@render form_item("L", leftForms, "OS")}
            </div>
        </div>
    {:else}
        <div class="flex flex-col gap-2">
            {@render form_item(undefined, forms)}
        </div>
    {/if}
</div>
