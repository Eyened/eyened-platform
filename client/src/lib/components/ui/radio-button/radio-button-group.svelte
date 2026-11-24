<script lang="ts" generics="T extends string">
    import { cn } from "$lib/utils.js";
    import RadioButton from "./radio-button.svelte";

    // Carbon radio button group: a label-01 legend 8 px above the items, 8 px between items.
    // Helper or error text follows the items; the error replaces the helper (Carbon).
    let {
        legendText,
        items,
        selected = $bindable(),
        disabled = false,
        describedBy,
        orientation = "horizontal",
        helperText,
        invalidText,
        readonly = false,
        class: className,
    }: {
        legendText: string;
        items: readonly { value: T; labelText: string }[];
        selected?: T;
        disabled?: boolean;
        /** Id of helper text for the whole group. */
        describedBy?: string;
        orientation?: "horizontal" | "vertical";
        helperText?: string;
        invalidText?: string;
        /** Focusable radios that don't change (Carbon Read-only states). */
        readonly?: boolean;
        class?: string;
    } = $props();

    const name = $props.id();
    const noteId = `${name}-note`;
    const note = $derived(invalidText ?? helperText);
</script>

<!-- A disabled fieldset disables every radio in it, so Tab skips them; the helper says why. -->
<fieldset
    class={cn("group/radios flex min-w-0 flex-col", className)}
    {disabled}
    aria-describedby={[describedBy, note ? noteId : undefined]
        .filter(Boolean)
        .join(" ") || undefined}
>
    <legend
        class="mb-2 text-label-01 text-text-secondary group-disabled/radios:text-text-disabled"
        >{legendText}</legend
    >
    <div
        class={orientation === "vertical"
            ? "flex flex-col gap-2"
            : "flex flex-wrap gap-2"}
    >
        {#each items as item (item.value)}
            <RadioButton
                {name}
                value={item.value}
                labelText={item.labelText}
                checked={selected === item.value}
                {readonly}
                invalid={invalidText !== undefined}
                onchange={() => (selected = item.value)}
            />
        {/each}
    </div>
    {#if note}
        <p
            id={noteId}
            class={cn(
                "mt-2 text-helper-text-01",
                invalidText ? "text-text-error" : "text-text-helper",
            )}
        >
            {note}
        </p>
    {/if}
</fieldset>
