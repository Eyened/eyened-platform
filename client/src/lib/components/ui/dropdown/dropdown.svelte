<script lang="ts">
    import { Label } from "$lib/components/ui/label/index.js";
    import * as Select from "$lib/components/ui/select/index.js";
    import { cn } from "$lib/utils.js";
    import WarningFilled from "carbon-icons-svelte/lib/WarningFilled.svelte";

    // Carbon Dropdown (carbon-components-svelte prop names) over ui/select, size lg (48 px), md (40 px) or sm (32 px);
    // menu items match the field height and the menu shows 5.5 items (@carbon/styles 1.117.0 list-box).
    // An item's optional `hint` (a shortcut key) follows its text in the menu.
    // `onselect` fires only when the user picks a different item; the optional `onclose` fires whenever the menu closes.
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        items,
        selectedId = $bindable(),
        labelText,
        type = "default",
        size = "lg",
        hideLabel = false,
        direction = "bottom",
        id = uid,
        onselect,
        onclose,
        placeholder,
        helperText,
        invalidText,
    }: {
        items: { id: string; text: string; hint?: string }[];
        selectedId?: string;
        labelText: string;
        type?: "default" | "inline";
        size?: "sm" | "md" | "lg";
        hideLabel?: boolean;
        direction?: "top" | "bottom";
        id?: string;
        onselect?: (selectedId: string) => void;
        onclose?: () => void;
        /** Shown while nothing is selected. */
        placeholder?: string;
        helperText?: string;
        /** Carbon invalid: a red outline, the warning icon and the error in place of the helper. */
        invalidText?: string;
    } = $props();

    const noteId = $derived(`${id}-note`);
    const note = $derived(invalidText ?? helperText);

    const heights = { sm: "h-8", md: "h-10", lg: undefined };
    const selectedText = $derived(
        items.find((i) => i.id === selectedId)?.text ?? "",
    );
</script>

<div
    class={type === "inline"
        ? "flex items-center gap-2"
        : "flex flex-col gap-2"}
>
    <Label
        id="{id}-label"
        for={id}
        class={hideLabel
            ? "sr-only"
            : type === "inline"
              ? "text-body-compact-01"
              : undefined}
    >
        {labelText}
    </Label>
    <Select.Root
        type="single"
        onOpenChange={(open) => {
            if (!open) onclose?.();
        }}
        items={items.map((i) => ({ value: i.id, label: i.text }))}
        bind:value={
            () => selectedId ?? "",
            (v) => {
                if (v === selectedId) return;
                selectedId = v;
                onselect?.(v);
            }
        }
    >
        <!-- label then trigger, so the name includes the selected value: "Status Not started" -->
        <Select.Trigger
            {id}
            aria-labelledby="{id}-label {id}"
            aria-invalid={invalidText ? "true" : undefined}
            aria-describedby={note ? noteId : undefined}
            variant={type}
            class={cn(
                heights[size],
                "aria-invalid:outline-2 aria-invalid:-outline-offset-2 aria-invalid:outline-support-error",
                invalidText && "pe-16",
            )}
        >
            {#if selectedText}{selectedText}{:else if placeholder}<span
                    class="text-text-placeholder">{placeholder}</span
                >{/if}
            {#if invalidText}
                <!-- Carbon puts the warning icon just before the chevron. -->
                <WarningFilled
                    aria-hidden="true"
                    class="pointer-events-none absolute end-10 top-1/2 -translate-y-1/2 text-support-error"
                />
            {/if}
        </Select.Trigger>
        <Select.Content
            variant={type}
            side={direction}
            class={size === "md"
                ? "max-h-55"
                : size === "sm"
                  ? "max-h-44"
                  : undefined}
        >
            {#each items as item (item.id)}
                <Select.Item
                    value={item.id}
                    label={item.text}
                    class={heights[size]}
                >
                    {item.text}
                    {#if item.hint}
                        <span class="ms-2 text-text-secondary">{item.hint}</span
                        >
                    {/if}
                </Select.Item>
            {/each}
        </Select.Content>
    </Select.Root>
    {#if note}
        <p
            id={noteId}
            class={cn(
                "text-helper-text-01",
                invalidText ? "text-text-error" : "text-text-helper",
            )}
        >
            {note}
        </p>
    {/if}
</div>
