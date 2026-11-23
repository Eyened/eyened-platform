<!--
@component
Add form: a "Form" Dropdown, starting on the task form in a task, else the last one used, then "Add form" for the selected viewport's target.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { Dropdown } from "$lib/components/ui/dropdown/index.js";
    import { HIDE_FROM_FORM_PANEL_NAMES } from "$lib/config/builtinFormSchemas";
    import { formSchemas } from "$lib/data/stores.svelte";
    import { resolveFormEntityScope } from "$lib/viewer-window/panelForm/formEntityScope";
    import {
        readLastFormSchema,
        writeLastFormSchema,
    } from "$lib/workspace/workspacePrefs";
    import { untrack } from "svelte";
    import type { FormSchemaGET } from "../../types/openapi_types";
    import {
        schemaName,
        targetsFor,
        type FormTarget,
        type OpenImage,
    } from "./formTargets";

    let {
        selectedImage,
        taskSchemaId,
        onadd,
    }: {
        /** The selected viewport's image; null while it is empty. */
        selectedImage: OpenImage | null;
        taskSchemaId?: number;
        onadd: (schema: FormSchemaGET, target: FormTarget) => void;
    } = $props();

    // ASSUMPTION: schemas sorted by name.
    const schemas = $derived(
        [...formSchemas.values()]
            .filter((s) => !HIDE_FROM_FORM_PANEL_NAMES.has(schemaName(s)))
            .sort((a, b) => schemaName(a).localeCompare(schemaName(b))),
    );
    let chosen: number | null = $state(
        untrack(() => taskSchemaId ?? readLastFormSchema()),
    );
    const schema = $derived(schemas.find((s) => s.id === chosen) ?? schemas[0]);
    const target = $derived(
        schema && selectedImage
            ? targetsFor(
                  [selectedImage],
                  resolveFormEntityScope(schema.entity_type),
              )[0]
            : undefined,
    );

    function add() {
        if (!schema || !target) return;
        writeLastFormSchema(schema.id);
        onadd(schema, target);
    }
</script>

{#if schema}
    <div class="flex flex-col gap-2 px-4 py-2">
        <Dropdown
            labelText="Form"
            size="md"
            items={schemas.map((s) => ({
                id: String(s.id),
                text: schemaName(s),
            }))}
            selectedId={String(schema.id)}
            onselect={(id) => (chosen = Number(id))}
        />
        <!-- ASSUMPTION: secondary; the set's primary action is in the header. -->
        <!-- data-add-form: where focus goes after a delete empties a group with no section around it. -->
        <Button
            variant="secondary"
            size="sm"
            class="self-start"
            data-add-form
            aria-disabled={!target || undefined}
            onclick={add}>Add form</Button
        >
        <p class="text-helper-text-01 text-text-helper">
            {target
                ? `For ${target.name} (selected)`
                : "Select a viewport with an image first."}
        </p>
    </div>
{/if}
