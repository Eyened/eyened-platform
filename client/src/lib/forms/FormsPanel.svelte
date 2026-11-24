<!--
@component
Grading (a task) or Forms (/view): the open images' forms by target. In a task, the task form's rows, then Other forms; on /view the groups. With more than one patient open, each part sits under a heading per patient.
Rows open their form in the window; "Grade" and Copy make one and open it.
-->
<script lang="ts">
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import {
        formAnnotations,
        formSchemas,
        formSchemasByName,
        subtasks,
    } from "$lib/data/stores.svelte";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import LayerSection from "$lib/layers/LayerSection.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import FormDeleteModal from "$lib/viewer-window/panelForm/FormDeleteModal.svelte";
    import { buildFormAnnotationCreatePayload } from "$lib/viewer-window/panelForm/formEntityScope";
    import type { ViewerWindowContext } from "$lib/viewer-window/viewerWindowContext.svelte";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import { getAllContexts, getContext } from "svelte";
    import { SvelteSet } from "svelte/reactivity";
    import type {
        FormAnnotationGET,
        FormSchemaGET,
    } from "../../types/openapi_types";
    import type { DebouncedSaver } from "$lib/saving/debouncedSaver.svelte";
    import AddForm from "./AddForm.svelte";
    import CommentsField from "./CommentsField.svelte";
    import { focusAfterFormDelete } from "./focusAfterFormDelete";
    import { FormCreator } from "./formCreator.svelte";
    import { formWindow } from "./formWindow.svelte";
    import FormGroups from "./FormGroups.svelte";
    import FormRow from "./FormRow.svelte";
    import {
        completeCount,
        completion,
        foldKeys,
        matchForms,
        openImages,
        schemaName,
        targetText,
        type FormGroup,
        type FormTarget,
        type TaskRow,
    } from "./formTargets";
    import { viewerFor } from "./formViewer";
    import { copyPayload, taskFormName } from "./taskForm";

    let { comments = null }: { comments?: DebouncedSaver<string> | null } =
        $props();

    const workspace = getContext<Workspace>("workspace");
    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );
    // Only the grade route sets it: with it this is Grading, without it Forms.
    const taskContext = getContext<TaskContext | undefined>("taskContext");
    const globalContext = getContext<GlobalContext>("globalContext");
    const userId = globalContext.user.id;
    const subTaskId = taskContext?.subTask.id;
    const taskName = taskContext
        ? taskFormName(taskContext.task.task_definition.config)
        : undefined;
    const taskSchema = $derived(
        taskName ? formSchemasByName.get(taskName) : undefined,
    );

    const images = $derived(
        openImages(workspace.catalogue, viewerWindowContext.images),
    );
    const matched = $derived(
        matchForms({
            forms: formAnnotations.values(),
            images,
            schemas: formSchemas,
            taskSchemaId: taskSchema?.id,
            userId,
            subTaskId,
        }),
    );
    const otherCount = $derived(
        matched.other.reduce((n, g) => n + g.forms.length, 0),
    );
    // Patients in strip order, each with its task rows and groups.
    const patients = $derived.by(() => {
        // eslint-disable-next-line svelte/prefer-svelte-reactivity -- a local rebuilt on each derive, never mutated later
        const byPatient = new Map<
            number,
            { name: string; rows: TaskRow[]; groups: FormGroup[] }
        >();
        for (const { instance } of images)
            if (!byPatient.has(instance.patient.id))
                byPatient.set(instance.patient.id, {
                    name: instance.patient.identifier,
                    rows: [],
                    groups: [],
                });
        for (const row of matched.taskRows ?? [])
            byPatient.get(row.target.patientId)?.rows.push(row);
        for (const group of matched.other)
            byPatient.get(group.target.patientId)?.groups.push(group);
        return [...byPatient.entries()];
    });
    const selectedImageId = $derived(
        workspace.slots[workspace.selected]?.imageId ?? null,
    );
    const selectedImage = $derived(
        images.find((image) => image.imageId === selectedImageId) ?? null,
    );

    const contexts = getAllContexts();
    const creator = new FormCreator(contexts);
    // Every header starts open; folds last for this page only.
    const folded = new SvelteSet<string>();
    let failure: HTMLElement | null = $state(null);
    // In a task Add form sits at the end of a long panel, so the notice at the top scrolls into view.
    $effect(() => {
        if (creator.failed) failure?.scrollIntoView({ block: "nearest" });
    });

    function toggle(key: string) {
        if (folded.has(key)) folded.delete(key);
        else folded.add(key);
    }

    /** A new form opens in the window; any fold that would hide its row opens too. */
    function unfold(created: FormAnnotationGET | null, target: FormTarget) {
        if (created) for (const key of foldKeys(target)) folded.delete(key);
    }

    function open(form: FormAnnotationGET, target: FormTarget) {
        formWindow.open(form, {
            source: "panel",
            canEdit: globalContext.canEdit(form),
            viewerContext: viewerFor(workspace, target),
            imageIds: target.imageIds,
            from: "viewer",
            contexts,
        });
    }

    async function grade(target: FormTarget) {
        if (!taskSchema) return;
        const name = schemaName(taskSchema);
        const created = await creator.create({
            key: `grade:${target.key}`,
            imageIds: target.imageIds,
            schemaName: name,
            message: `Added ${name} for ${targetText(target, matched.multiPatient)}`,
            payload: buildFormAnnotationCreatePayload({
                formSchemaId: taskSchema.id,
                scope: target.scope,
                ctx: target.ctx,
                subTaskId,
            }),
            viewerContext: viewerFor(workspace, target),
        });
        unfold(created, target);
    }

    // In a task the new form joins the set, as Grade's does.
    async function add(schema: FormSchemaGET, target: FormTarget) {
        const name = schemaName(schema);
        const created = await creator.create({
            key: "add",
            imageIds: target.imageIds,
            schemaName: name,
            message: `Added ${name} for ${targetText(target, matched.multiPatient)}`,
            payload: buildFormAnnotationCreatePayload({
                formSchemaId: schema.id,
                scope: target.scope,
                ctx: target.ctx,
                subTaskId,
            }),
            viewerContext: viewerFor(workspace, target),
        });
        unfold(created, target);
    }

    async function copy(form: FormAnnotationGET, target: FormTarget) {
        const schema = formSchemas.get(form.form_schema_id);
        const name = schema
            ? schemaName(schema)
            : `Form ${form.form_schema_id}`;
        const created = await creator.create({
            key: `copy:${form.id}`,
            imageIds: target.imageIds,
            schemaName: name,
            message: `Copied ${name}`,
            payload: copyPayload(form, subTaskId),
            viewerContext: viewerFor(workspace, target),
        });
        unfold(created, target);
    }

    let deleting: FormAnnotationGET | null = $state(null);
    let deleteOpen = $state(false);
    let fallback = () => {};
    function askDelete(form: FormAnnotationGET, control: HTMLElement) {
        fallback = focusAfterFormDelete(control);
        deleting = form;
        deleteOpen = true;
    }
</script>

{#snippet groups(list: FormGroup[], level: 3 | 4 | 5)}
    <FormGroups
        groups={list}
        {level}
        {folded}
        {userId}
        {selectedImageId}
        onopen={open}
        oncopy={copy}
        ondelete={askDelete}
    />
{/snippet}

{#snippet taskRowList(list: TaskRow[], schema: FormSchemaGET, depth: 1 | 2)}
    <ul>
        {#each list as { target, form } (target.key)}
            <li>
                <!-- Task rows hold only my forms, so a form can be deleted. -->
                <FormRow
                    name={target.name}
                    {target}
                    {form}
                    completion={form ? completion(form, schema) : null}
                    open={form !== null && formWindow.formId === form.id}
                    current={selectedImageId !== null &&
                        target.imageIds.includes(selectedImageId)}
                    {depth}
                    canDelete={form !== null}
                    onopen={() => (form ? open(form, target) : grade(target))}
                    oncopy={() => form && copy(form, target)}
                    ondelete={(control) => form && askDelete(form, control)}
                />
            </li>
        {/each}
    </ul>
{/snippet}

{#snippet addForm()}
    <AddForm {selectedImage} taskSchemaId={taskSchema?.id} onadd={add} />
{/snippet}

<div class="flex flex-col pb-4" data-forms-panel>
    {#if formWindow.blocked === "panel"}
        <!-- Focus stays on the row; clicking it again tries again. -->
        <div class="px-4 pb-2">
            <InlineNotification
                title="Form window blocked"
                subtitle="Allow pop-ups for this site in your browser, then open the form again."
                onclose={() => formWindow.dismissBlocked()}
            />
        </div>
    {/if}
    {#if creator.failed}
        <div class="px-4 pb-2">
            <InlineNotification
                bind:ref={failure}
                title="Couldn't add {creator.failed}"
                onclose={() => creator.dismiss()}
            />
        </div>
    {/if}
    <!-- Always mounted, so each message is announced; focus stays on the button pressed. -->
    <p role="status" class="sr-only">{creator.message}</p>
    {#if !taskContext}
        <!-- /view: Add form is the main way forms are made, so it comes first. -->
        {@render addForm()}
    {/if}
    {#if taskContext}
        {#if comments}
            <CommentsField
                saver={comments}
                initial={taskContext.subTask.comments ?? ""}
                readonly={subtasks.get(taskContext.subTask.id)
                    ?.can_edit_status_and_comments !== true}
            />
        {/if}
        {#if taskName && !taskSchema}
            <div class="px-4 pb-2">
                <InlineNotification
                    kind="warning"
                    title={`This task's form "${taskName}" wasn't found`}
                    subtitle="Ask the task owner."
                />
            </div>
        {:else if matched.taskSchema && matched.taskRows}
            {@const schema = matched.taskSchema}
            {@const rows = matched.taskRows}
            <div data-layer-section="task-form">
                <LayerSection
                    title={schemaName(schema)}
                    count="{completeCount(
                        rows,
                        schema,
                    )} of {rows.length} complete"
                    open={!folded.has("task")}
                    ontoggle={() => toggle("task")}
                >
                    {#if matched.multiPatient}
                        {#each patients as [patientId, patient] (patientId)}
                            {#if patient.rows.length > 0}
                                <LayerSection
                                    title={patient.name}
                                    count="{completeCount(
                                        patient.rows,
                                        schema,
                                    )} of {patient.rows.length} complete"
                                    level={4}
                                    open={!folded.has(
                                        `task:patient:${patientId}`,
                                    )}
                                    ontoggle={() =>
                                        toggle(`task:patient:${patientId}`)}
                                >
                                    {@render taskRowList(
                                        patient.rows,
                                        schema,
                                        2,
                                    )}
                                </LayerSection>
                            {/if}
                        {/each}
                    {:else}
                        {@render taskRowList(rows, schema, 1)}
                    {/if}
                </LayerSection>
            </div>
        {/if}
        <div data-layer-section="other-forms">
            <LayerSection
                title="Other forms"
                count={otherCount}
                open={!folded.has("other")}
                ontoggle={() => toggle("other")}
                empty="No forms for these images yet."
            >
                {#if matched.multiPatient}
                    {#each patients as [patientId, patient] (patientId)}
                        {#if patient.groups.length > 0}
                            <LayerSection
                                title={patient.name}
                                level={4}
                                open={!folded.has(`other:patient:${patientId}`)}
                                ontoggle={() =>
                                    toggle(`other:patient:${patientId}`)}
                            >
                                {@render groups(patient.groups, 5)}
                            </LayerSection>
                        {/if}
                    {/each}
                {:else}
                    {@render groups(matched.other, 4)}
                {/if}
            </LayerSection>
        </div>
    {:else if matched.multiPatient}
        {#each patients as [patientId, patient] (patientId)}
            <div data-layer-section="patient">
                <LayerSection
                    title={patient.name}
                    open={!folded.has(`patient:${patientId}`)}
                    ontoggle={() => toggle(`patient:${patientId}`)}
                >
                    {@render groups(patient.groups, 4)}
                </LayerSection>
            </div>
        {/each}
        {#if matched.other.length === 0}
            <p class="px-4 text-label-01 text-text-secondary">
                No forms for these images yet.
            </p>
        {/if}
    {:else}
        <!-- ASSUMPTION: with one patient the groups sit at level 3, so no heading level is skipped under "Forms". -->
        {@render groups(matched.other, 3)}
        {#if matched.other.length === 0}
            <p class="px-4 text-label-01 text-text-secondary">
                No forms for these images yet.
            </p>
        {/if}
    {/if}
    {#if taskContext}
        {@render addForm()}
    {/if}
</div>
<FormDeleteModal
    form={deleting}
    bind:open={deleteOpen}
    onfallback={() => fallback()}
/>
