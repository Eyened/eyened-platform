<!--
@component
A form from its JSON Schema: the root's questions on Carbon controls; a question's error shows once focus has left it, or for all after a Mark ready attempt.
-->
<script lang="ts">
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { SvelteSet } from "svelte/reactivity";
    import { fieldErrors, NOT_APPLICABLE } from "./fieldErrors";
    import FieldList from "./FieldList.svelte";
    import { fieldKind } from "./fieldKind";
    import { setFormContext } from "./formContext";
    import { checkForm } from "./formValidator";
    import SchemaField from "./SchemaField.svelte";
    import { deref, type JSONSchema } from "./schemaType";

    let {
        schema,
        value,
        onchange,
        canEdit = true,
        vertical = true,
        markReadyAttempted = false,
    }: {
        /** The form schema as stored; `$ref`s are followed where they are drawn. */
        schema: JSONSchema;
        value: unknown;
        onchange: (value: unknown) => void;
        canEdit?: boolean;
        vertical?: boolean;
        /** "Go back" in "n forms aren't complete" was pressed in this set. */
        markReadyAttempted?: boolean;
    } = $props();

    const check = $derived(checkForm(schema, value));
    const messages = $derived(fieldErrors(check.errors, value));
    const touched = new SvelteSet<string>();
    let reveal = $state<{ path: string } | null>(null);
    const rootNode = $derived(deref(schema, schema));

    const shown = (path: string) => touched.has(path) || markReadyAttempted;

    setFormContext({
        get root() {
            return schema;
        },
        get canEdit() {
            return canEdit;
        },
        get vertical() {
            return vertical;
        },
        get reveal() {
            return reveal;
        },
        // Another answer made this one not apply, so it shows at once.
        message: (path) => {
            const text = messages.get(path);
            return text === NOT_APPLICABLE || shown(path) ? text : undefined;
        },
        shown,
        ruledOut: (path) => check.ruledOut.has(path),
        requiredNow: (path) => check.requiredNow.has(path),
        missing: (path) =>
            check.errors.filter(
                (e) => e.type === "required" && e.path.startsWith(`${path}/`),
            ).length,
        touch: (path) => touched.add(path),
    });
</script>

<div class="flex flex-col gap-6">
    {#if check.schemaError}
        <InlineNotification
            role="status"
            title="This form's schema has an error, so answers aren't checked"
        />
    {/if}
    {#if rootNode && fieldKind(rootNode, schema) === "section"}
        {#if messages.get("") && shown("")}
            <p class="text-helper-text-01 text-text-error">
                {messages.get("")}
            </p>
        {/if}
        <FieldList schema={rootNode} {value} path="" depth={0} {onchange} />
    {:else}
        <SchemaField {schema} {value} path="" name="Answer" {onchange} />
    {/if}
</div>
