<!--
@component
Target groups of form rows, newest first: Grading's Other forms and the Forms panel.
A group's wrapper outlines its target's viewports while the pointer or focus is in it.
-->
<script lang="ts">
    import { formSchemas } from "$lib/data/stores.svelte";
    import LayerSection from "$lib/layers/LayerSection.svelte";
    import { openForm } from "$lib/viewer-window/panelForm/openForm.svelte";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import { getContext } from "svelte";
    import type { SvelteSet } from "svelte/reactivity";
    import type { FormAnnotationGET } from "../../types/openapi_types";
    import FormRow from "./FormRow.svelte";
    import {
        completion,
        schemaName,
        type FormGroup,
        type FormTarget,
    } from "./formTargets";

    let {
        groups,
        level,
        folded,
        userId,
        selectedImageId,
        onopen,
        oncopy,
        ondelete,
    }: {
        groups: FormGroup[];
        level: 3 | 4 | 5;
        folded: SvelteSet<string>;
        userId: number;
        selectedImageId: string | null;
        onopen: (form: FormAnnotationGET, target: FormTarget) => void;
        oncopy: (form: FormAnnotationGET, target: FormTarget) => void;
        ondelete: (form: FormAnnotationGET, control: HTMLElement) => void;
    } = $props();

    const workspace = getContext<Workspace>("workspace");

    function toggle(key: string) {
        if (folded.has(key)) folded.delete(key);
        else folded.add(key);
    }
</script>

{#each groups as group (group.target.key)}
    {@const target = group.target}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
        data-layer-section="form-group"
        onpointerenter={() => workspace.highlight(target.imageIds)}
        onpointerleave={() => workspace.highlight([])}
        onfocusin={() => workspace.highlight(target.imageIds)}
        onfocusout={() => workspace.highlight([])}
    >
        <LayerSection
            title={target.group}
            count={group.forms.length}
            {level}
            open={!folded.has(target.key)}
            ontoggle={() => toggle(target.key)}
        >
            <ul>
                {#each group.forms as form (form.id)}
                    {@const schema = formSchemas.get(form.form_schema_id)}
                    {#if schema}
                        <li>
                            <FormRow
                                name={schemaName(schema)}
                                {target}
                                {form}
                                completion={completion(form, schema)}
                                open={openForm.id === form.id}
                                current={selectedImageId !== null &&
                                    target.imageIds.includes(selectedImageId)}
                                depth={level === 5 ? 3 : 2}
                                creator={form.creator.id === userId
                                    ? undefined
                                    : form.creator.name}
                                dated
                                canDelete={form.creator.id === userId}
                                outline={false}
                                onopen={() => onopen(form, target)}
                                oncopy={() => oncopy(form, target)}
                                ondelete={(control) => ondelete(form, control)}
                            />
                        </li>
                    {/if}
                {/each}
            </ul>
        </LayerSection>
    </div>
{/each}
