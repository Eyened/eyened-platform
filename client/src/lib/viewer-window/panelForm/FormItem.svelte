<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { createFormAnnotation } from "$lib/data";
    import { formSchemas } from "$lib/data/stores.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import Copy from "carbon-icons-svelte/lib/Copy.svelte";
    import Launch from "carbon-icons-svelte/lib/Launch.svelte";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";
    import { getAllContexts, getContext } from "svelte";
    import type { FormAnnotationGET } from "../../../types/openapi_types";
    import { formWindow } from "$lib/forms/formWindow.svelte";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import { openImages, targetOf } from "$lib/forms/formTargets";
    import { viewerFor } from "$lib/forms/formViewer";
    import type { ViewerWindowContext } from "$lib/viewer-window/viewerWindowContext.svelte";
    import type { Workspace } from "$lib/workspace/workspace.svelte";

    const taskContext = getContext<TaskContext>("taskContext");
    const globalContext = getContext<GlobalContext>("globalContext");
    // Set only in the viewer, where this card sits in the Add images overlay.
    const workspace = getContext<Workspace | undefined>("workspace");
    const viewerWindowContext = getContext<ViewerWindowContext | undefined>(
        "viewerWindowContext",
    );
    const contexts = getAllContexts();

    interface Props {
        form: FormAnnotationGET;
        /** Where a blocked window's notice shows. */
        source: string;
        ondelete: (form: FormAnnotationGET) => void;
    }

    let { form, source, ondelete }: Props = $props();

    const formSchema = $derived(formSchemas.get(form.form_schema_id)!);

    const canEditForm = globalContext.canEdit(form);

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
        // In the viewer the form's point fields get the viewport showing its target, as Grading's rows do.
        const target =
            workspace && viewerWindowContext
                ? targetOf(
                      form,
                      formSchema,
                      openImages(
                          workspace.catalogue,
                          viewerWindowContext.images,
                      ),
                  )
                : null;
        formWindow.open(form, {
            source,
            canEdit: canEditForm,
            viewerContext:
                workspace && target ? viewerFor(workspace, target) : undefined,
            imageIds: target?.imageIds ?? [],
            from: workspace ? "viewer" : "browse",
            contexts,
        });
    }

    const meta = $derived(
        [
            `#${form.id}`,
            form.form_annotation_reference_id
                ? `copy of #${form.form_annotation_reference_id}`
                : null,
            form.creator?.id === globalContext.user.id
                ? "yours"
                : form.creator
                  ? `${form.creator.name}'s`
                  : null,
            form.date_inserted?.slice(0, 10),
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
        <!-- Shrinks and wraps a long form name so Copy and Delete stay in the card. -->
        <Button
            variant="ghost"
            size="sm"
            class="min-w-0 shrink"
            onclick={() => openInNewWindow(form)}
        >
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
    <p
        class="flex items-center gap-2 px-4 pb-2 text-label-01 text-text-secondary"
    >
        {#if !canEditForm}<Tag>Read-only</Tag>{/if}{meta}
    </p>
</div>
