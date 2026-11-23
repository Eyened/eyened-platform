<!--
@component
A Grading or Forms row: a Layers row for one form, or for a target whose task form isn't made yet ("Grade").
The blue bar, tint and Document icon mark the form open in the window; the grey bar the selected viewport's target.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import LayerRow from "$lib/layers/LayerRow.svelte";
    import { formAnnotationSavers } from "$lib/saving/formAnnotationSavers";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import CheckmarkFilled from "carbon-icons-svelte/lib/CheckmarkFilled.svelte";
    import Copy from "carbon-icons-svelte/lib/Copy.svelte";
    import Document from "carbon-icons-svelte/lib/Document.svelte";
    import Incomplete from "carbon-icons-svelte/lib/Incomplete.svelte";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";
    import { getContext } from "svelte";
    import type { FormAnnotationGET } from "../../types/openapi_types";
    import type { Completion, FormTarget } from "./formTargets";

    let {
        name,
        target,
        form,
        completion,
        open,
        current,
        depth,
        creator,
        dated = false,
        canDelete,
        outline = true,
        onopen,
        oncopy,
        ondelete,
    }: {
        /** The target on task rows, the schema on Other forms rows. */
        name: string;
        target: FormTarget;
        /** Null on a "Grade" row. */
        form: FormAnnotationGET | null;
        completion: Completion | null;
        /** Shown in the form window. */
        open: boolean;
        /** The target holds the selected viewport's image. */
        current: boolean;
        depth: 1 | 2 | 3;
        /** Someone else's form: their name as a tag. */
        creator?: string;
        /** Other forms rows add the date, so two forms of one schema read apart. */
        dated?: boolean;
        canDelete: boolean;
        /** False in a target group, whose wrapper outlines the target. */
        outline?: boolean;
        onopen: () => void;
        oncopy: () => void;
        ondelete: (control: HTMLElement) => void;
    } = $props();

    const workspace = getContext<Workspace>("workspace");
    const failed = $derived(
        form ? formAnnotationSavers.get(form.id)?.state === "error" : false,
    );
    const state = $derived(
        form === null
            ? "not graded"
            : completion === "complete"
              ? "complete"
              : "not complete",
    );
    const date = $derived(form?.date_inserted.slice(0, 10) ?? "");
    // The states in words after the visible name (WCAG 2.5.3).
    const nameLabel = $derived(
        [
            name,
            dated ? date : null,
            state,
            failed ? "couldn't save" : null,
            open ? "in window" : null,
            // The word "Grade" also creates the form, so voice control's "click Grade" finds this button.
            form === null ? "grade" : null,
        ]
            .filter(Boolean)
            .join(", "),
    );
    const tooltip = $derived(
        [
            target.full,
            state.charAt(0).toUpperCase() + state.slice(1),
            form ? `#${form.id} · ${form.creator.name} · ${date}` : null,
            form?.form_annotation_reference_id
                ? `copy of #${form.form_annotation_reference_id}`
                : null,
        ]
            .filter(Boolean)
            .join("\n"),
    );
    const show = () => outline && workspace.highlight(target.imageIds);
    const hide = () => outline && workspace.highlight([]);
</script>

<LayerRow
    label={name}
    {name}
    {nameLabel}
    {tooltip}
    selected={open}
    visible={current}
    {current}
    pressed={false}
    {depth}
    onselect={onopen}
    onpointerenter={show}
    onpointerleave={hide}
    onfocusin={show}
    onfocusout={hide}
>
    {#snippet tags()}
        {#if open}
            <!-- Not colour alone: the icon stays while the form is in the window. -->
            <Document aria-hidden="true" class="shrink-0" />
        {/if}
        {#if creator}<Tag>{creator}</Tag>{/if}
        {#if form?.form_annotation_reference_id}<Tag>copy</Tag>{/if}
        {#if form === null}
            <!-- A pointer shortcut for the name button, which keyboard and screen reader users press; hidden so it isn't read twice. -->
            <span
                aria-hidden="true"
                class="shrink-0 cursor-pointer px-1 text-label-01 text-link-primary hover:underline"
                onclick={onopen}>Grade</span
            >
        {:else if completion === "complete"}
            <CheckmarkFilled
                aria-hidden="true"
                class="shrink-0 text-status-green"
            />
        {:else}
            <Incomplete aria-hidden="true" class="shrink-0 text-status-blue" />
        {/if}
        {#if failed}<Tag type="red">Couldn't save</Tag>{/if}
    {/snippet}
    {#snippet icons()}
        {#if form}
            <!-- These appear where "Grade" was, so the second click of a double-click on Grade must not reach them. -->
            <IconButton
                size="icon-xs"
                label="Copy"
                onclick={(e) => e.detail < 2 && oncopy()}
            >
                <Copy />
            </IconButton>
            {#if canDelete}
                <IconButton
                    size="icon-xs"
                    label="Delete form"
                    onclick={(e) =>
                        e.detail < 2 &&
                        ondelete(e.currentTarget as HTMLElement)}
                >
                    <TrashCan />
                </IconButton>
            {/if}
        {/if}
    {/snippet}
</LayerRow>
