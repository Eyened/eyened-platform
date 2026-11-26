<!--
@component
A form from its JSON Schema: the root's questions on Carbon controls; a question's error shows once focus has left it, or for all after a Mark ready attempt.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { tick } from "svelte";
    import { SvelteSet } from "svelte/reactivity";
    import {
        fieldErrors,
        MISSING,
        NOT_APPLICABLE,
        NOT_APPLICABLE_READ_ONLY,
    } from "./fieldErrors";
    import FieldList from "./FieldList.svelte";
    import { fieldKind, titleAt } from "./fieldKind";
    import { FOCUSABLE, setFormContext } from "./formContext";
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

    let element = $state<HTMLElement | null>(null);

    // One link per question with a message; the notice goes when none are left.
    const links = $derived(
        markReadyAttempted
            ? [...messages].map(([path, message]) => ({
                  path,
                  message,
                  title: titleAt(schema, path),
              }))
            : [],
    );
    const noticeTitle = $derived.by(() => {
        const n = links.length;
        if (links.every((l) => l.message === MISSING)) {
            return n === 1
                ? "1 required question isn't answered"
                : `${n} required questions aren't answered`;
        }
        return n === 1
            ? "1 answer needs attention"
            : `${n} answers need attention`;
    });

    /** Unfolds the sections holding the question, then focuses it; a form-level message focuses the first question. */
    async function go(path: string) {
        reveal = { path };
        await tick();
        requestAnimationFrame(() => {
            const fields = [
                ...(element?.querySelectorAll<HTMLElement>(
                    "[data-field-path]",
                ) ?? []),
            ];
            // ASSUMPTION: "focus the form" means its first question, as an error summary links a form-level error to the first field.
            const field =
                path === ""
                    ? fields[0]
                    : fields.find((f) => f.dataset.fieldPath === path);
            field?.querySelector<HTMLElement>(FOCUSABLE)?.focus();
        });
    }

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
            if (text === NOT_APPLICABLE)
                return canEdit ? text : NOT_APPLICABLE_READ_ONLY;
            return shown(path) ? text : undefined;
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

<div bind:this={element} class="flex flex-col gap-6">
    <!-- The title alone is announced on each change; an alert would re-read every link while the grader fixes answers. -->
    <p role="status" class="sr-only">{links.length > 0 ? noticeTitle : ""}</p>
    {#if links.length > 0}
        <InlineNotification kind="error" role="none" title={noticeTitle}>
            <ul class="mt-2 flex flex-col gap-1">
                {#each links as link (link.path)}
                    <li>
                        <Button variant="link" onclick={() => go(link.path)}
                            >{link.title}</Button
                        >
                    </li>
                {/each}
            </ul>
        </InlineNotification>
    {/if}
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
