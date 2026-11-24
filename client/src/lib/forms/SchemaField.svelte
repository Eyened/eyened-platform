<!--
@component
One question: its control by kind, " (required)", helper text, the error once it shows, and × Clear when answered.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import { tick } from "svelte";
    import { fieldKind, questionTitle, storedType } from "./fieldKind";
    import { FOCUSABLE, formContext } from "./formContext";
    import CheckboxGroupField from "./fields/CheckboxGroupField.svelte";
    import DropdownField from "./fields/DropdownField.svelte";
    import GroupListField from "./fields/GroupListField.svelte";
    import MultiSelectField from "./fields/MultiSelectField.svelte";
    import NumberField from "./fields/NumberField.svelte";
    import RadioField from "./fields/RadioField.svelte";
    import SectionField from "./fields/SectionField.svelte";
    import TextField from "./fields/TextField.svelte";
    import ValueListField from "./fields/ValueListField.svelte";
    import PointField from "./PointField.svelte";
    import { deref } from "./schemaType";

    // Deeper than this, a schema that refers to itself would draw without end.
    const MAX_DEPTH = 16;

    let {
        schema,
        value,
        path,
        name,
        required = false,
        depth = 0,
        title: titleOverride,
        onremove,
        onchange,
    }: {
        schema: unknown;
        value: unknown;
        path: string;
        /** Words for the question when its schema has none. */
        name: string;
        required?: boolean;
        depth?: number;
        /** Words that replace the schema's, e.g. "Note 2" in a list. */
        title?: string;
        /** A list entry: × removes the entry instead of clearing the answer. */
        onremove?: () => void;
        onchange: (value: unknown) => void;
    } = $props();

    const ctx = formContext();
    const node = $derived(deref(schema, ctx.root));
    const kind = $derived(
        node && depth <= MAX_DEPTH ? fieldKind(node, ctx.root) : "unsupported",
    );
    const title = $derived(titleOverride ?? questionTitle(node, name));
    const label = $derived(required ? `${title} (required)` : title);
    const helperText = $derived(
        node?.title && node.description && node.description !== node.title
            ? node.description
            : undefined,
    );
    const invalidText = $derived(ctx.message(path));
    const readonly = $derived(!ctx.canEdit);
    const hidden = $derived(ctx.ruledOut(path) && value === undefined);
    const options = $derived((node?.enum ?? []) as readonly unknown[]);
    const itemOptions = $derived(
        (deref(node?.items, ctx.root)?.enum ?? []) as readonly unknown[],
    );
    const removable = $derived(
        ctx.canEdit &&
            (onremove !== undefined ||
                (value !== undefined &&
                    // A ruled-out section that still holds answers is cleared as a whole.
                    (kind !== "section" || ctx.ruledOut(path)) &&
                    kind !== "point" &&
                    kind !== "unsupported")),
    );
    let container = $state<HTMLElement | null>(null);

    /** Leaving the question marks it touched; moving inside it (radio to radio) or into its own menu doesn't. */
    function onfocusout(e: FocusEvent) {
        const to = e.relatedTarget as Element | null;
        if (to && (container?.contains(to) || to.closest('[role="listbox"]')))
            return;
        ctx.touch(path);
    }

    async function clear() {
        if (onremove) {
            onremove();
            return;
        }
        onchange(undefined);
        await tick();
        container?.querySelector<HTMLElement>(FOCUSABLE)?.focus();
    }
</script>

{#if !hidden}
    <div
        bind:this={container}
        data-field-path={path}
        class="flex items-start gap-2"
        {onfocusout}
    >
        <div class="min-w-0 flex-1">
            {#if !node || kind === "unsupported"}
                <p class="text-body-compact-01 text-text-secondary">
                    {title}: This question can't be shown.
                </p>
            {:else if kind === "radios"}
                <RadioField
                    {options}
                    vertical={ctx.vertical}
                    {value}
                    {onchange}
                    {label}
                    {helperText}
                    {invalidText}
                    {readonly}
                />
            {:else if kind === "yesno"}
                <RadioField
                    options={[true, false]}
                    labels={["Yes", "No"]}
                    vertical={ctx.vertical}
                    {value}
                    {onchange}
                    {label}
                    {helperText}
                    {invalidText}
                    {readonly}
                />
            {:else if kind === "dropdown"}
                <DropdownField
                    {options}
                    {value}
                    {onchange}
                    {label}
                    {helperText}
                    {invalidText}
                    {readonly}
                />
            {:else if kind === "checkboxes"}
                <CheckboxGroupField
                    options={itemOptions}
                    {value}
                    {onchange}
                    {label}
                    {helperText}
                    {invalidText}
                    {readonly}
                />
            {:else if kind === "multiselect"}
                <MultiSelectField
                    options={itemOptions}
                    {value}
                    {onchange}
                    {label}
                    {helperText}
                    {invalidText}
                    {readonly}
                />
            {:else if kind === "number"}
                <NumberField
                    integer={storedType(node) === "integer"}
                    errorsShown={ctx.shown(path)}
                    {value}
                    {onchange}
                    {label}
                    {helperText}
                    {invalidText}
                    {readonly}
                />
            {:else if kind === "text"}
                <TextField
                    {value}
                    {onchange}
                    {label}
                    {helperText}
                    {invalidText}
                    {readonly}
                />
            {:else if kind === "section"}
                <SectionField
                    {node}
                    {value}
                    {path}
                    {depth}
                    {label}
                    {invalidText}
                    {onchange}
                />
            {:else if kind === "group-list"}
                <GroupListField
                    {node}
                    {path}
                    {depth}
                    {value}
                    {onchange}
                    {label}
                    {helperText}
                    {invalidText}
                    {readonly}
                />
            {:else if kind === "value-list"}
                <ValueListField
                    {node}
                    {path}
                    {depth}
                    {value}
                    {onchange}
                    {label}
                    {helperText}
                    {invalidText}
                    {readonly}
                />
            {:else if kind === "point"}
                <PointField
                    schema={node}
                    {value}
                    {onchange}
                    canEdit={ctx.canEdit}
                    fieldPath={path || "point"}
                    {title}
                    {required}
                    {helperText}
                    {invalidText}
                />
            {:else}
                <p class="text-body-compact-01 text-text-secondary">
                    {title}: This question can't be shown.
                </p>
            {/if}
        </div>
        {#if removable}
            <IconButton
                size="icon-xs"
                label={onremove ? `Remove ${title}` : `Clear answer: ${title}`}
                data-clear
                onclick={clear}><Close /></IconButton
            >
        {/if}
    </div>
{/if}
