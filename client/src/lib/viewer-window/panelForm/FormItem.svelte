<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { createFormAnnotation } from "$lib/data";
    import { formSchemas } from "$lib/data/stores.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import Copy from "carbon-icons-svelte/lib/Copy.svelte";
    import Launch from "carbon-icons-svelte/lib/Launch.svelte";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";
    import { getContext } from "svelte";
    import type { FormAnnotationGET } from "../../../types/openapi_types";
    import { openFormInNewWindow } from "./openFormInNewWindow";

    const taskContext = getContext<TaskContext>("taskContext");
    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");

    interface Props {
        form: FormAnnotationGET;
        ondelete: (form: FormAnnotationGET) => void;
    }

    let { form, ondelete }: Props = $props();

    const formSchema = $derived(formSchemas.get(form.form_schema_id)!);

    const canEditForm = globalContext.canEdit(form);

    const date = form.date_inserted ?? "";

    async function duplicate() {
        await createFormAnnotation({
            form_schema_id: form.form_schema_id,
            patient_id: form.patient_id,
            study_id: form.study_id ?? undefined,
            image_id: form.image_id!,
            laterality: form.laterality ?? undefined,
            sub_task_id:
                taskContext?.subTask?.id ?? form.sub_task_id ?? undefined,
            form_data: form.form_data,
            form_annotation_reference_id: form.id,
        });
    }

    function openInNewWindow(form: FormAnnotationGET) {
        openFormInNewWindow(form, canEditForm, viewerContext);
    }

    function formatDateTime(dateString: string) {
        const date = new Date(dateString);
        return date.toLocaleString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    const meta = $derived(
        [
            form.form_annotation_reference_id
                ? `${form.form_annotation_reference_id} → ${form.id}`
                : `${form.id}`,
            form.creator?.name,
            formatDateTime(date),
        ]
            .filter(Boolean)
            .join(" · "),
    );
</script>

<!-- A saved form: Open is the card's action, in its top-left corner; Copy and Delete are icon buttons. -->
<div
    class="flex flex-col bg-layer-01 in-dialog:bg-layer-02 in-study:bg-layer-02 in-dialog:in-study:bg-layer-03"
>
    <div class="flex items-center">
        <Button variant="ghost" size="sm" onclick={() => openInNewWindow(form)}>
            Open {formSchema.name}
            <Launch aria-hidden="true" />
        </Button>
        <IconButton label="Copy" class="ms-auto size-8" onclick={duplicate}>
            <Copy />
        </IconButton>
        <IconButton
            label="Delete form"
            class="size-8"
            disabled={!canEditForm}
            onclick={() => ondelete(form)}
        >
            <TrashCan />
        </IconButton>
    </div>
    <p class="px-4 pb-2 text-label-01 text-text-secondary">{meta}</p>
</div>
