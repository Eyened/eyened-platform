<!--
@component
The form window's page: the form, or Opening…, Grade, "Nothing to grade here" or the closed state.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import {
        deviceText,
        eyeLabel,
        modalityField,
    } from "$lib/workspace/imageMeta";
    import { BitsConfig } from "bits-ui";
    import { getContext } from "svelte";
    import type { WindowView } from "./formWindow.svelte";
    import { ABOUT, windowHeading } from "./formTargets";
    import FormWindowForm from "./FormWindowForm.svelte";

    let { view, portalTo }: { view: WindowView; portalTo: Element } = $props();
    const taskContext = getContext<TaskContext | undefined>("taskContext");
    const setNumber = taskContext ? taskContext.subTaskIndex + 1 : null;
</script>

<BitsConfig defaultPortalTo={portalTo}>
    {#if view.kind === "form"}
        <FormWindowForm
            form={view.form}
            canEdit={view.canEdit}
            viewerContext={view.viewerContext}
        />
    {:else}
        <!-- Each view starts with an h1 (tabindex -1) that takes focus when the view changes under it. -->
        <div class="flex flex-col gap-2 p-4">
            {#if view.kind === "opening"}
                <h1 tabindex="-1" class="text-body-01 text-text-secondary">
                    Opening…
                </h1>
            {:else if view.kind === "failed"}
                <h1 tabindex="-1" class="sr-only">Form window</h1>
                <InlineNotification title="Couldn't create the form" />
            {:else if view.kind === "grade"}
                <p class="text-label-01 text-text-secondary">
                    {[
                        taskContext
                            ? `Set ${setNumber} of ${taskContext.task.num_tasks}`
                            : null,
                        view.schemaName,
                    ]
                        .filter(Boolean)
                        .join(" · ")}
                </p>
                <h1 tabindex="-1" class="text-heading-03 text-text-primary">
                    {windowHeading(view.scope, {
                        patient: view.meta.patient.identifier,
                        eye: eyeLabel(view.meta.laterality),
                        modality: modalityField(view.meta),
                        date: view.meta.study.date,
                    })}
                </h1>
                <p class="text-body-compact-01 text-text-secondary">
                    {[
                        view.scope === "ImageInstance"
                            ? deviceText(view.meta)
                            : "",
                        ABOUT[view.scope],
                    ]
                        .filter(Boolean)
                        .join(" · ")}
                </p>
                {#if view.failed}
                    <InlineNotification title="Couldn't create the form" />
                    <Button class="self-start" onclick={view.ongrade}
                        >Try again</Button
                    >
                {:else}
                    <p class="text-body-01 text-text-primary">Not graded yet</p>
                    <Button class="self-start" onclick={view.ongrade}
                        >Grade</Button
                    >
                {/if}
            {:else if view.kind === "nothing"}
                <h1 tabindex="-1" class="text-heading-03 text-text-primary">
                    Nothing to grade here
                </h1>
                <p class="text-body-01 text-text-secondary">
                    Set {setNumber} has no image for this form. Pick a form in Grading.
                </p>
            {:else}
                <h1 tabindex="-1" class="text-body-01 text-text-primary">
                    The viewer closed. Open a form from the viewer to continue.
                </h1>
            {/if}
        </div>
    {/if}
</BitsConfig>
