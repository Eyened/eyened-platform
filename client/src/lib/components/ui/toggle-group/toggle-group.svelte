<script lang="ts">
    import { ToggleGroup as ToggleGroupPrimitive } from "bits-ui";
    import { cn } from "$lib/utils.js";

    // Single-select toggle group (Carbon has none): one tab stop, arrow keys inside. No item is selected
    // when `value` matches none; pressing the selected item keeps it selected.
    let {
        value,
        onchange,
        items,
        label,
        class: className,
    }: {
        value: string;
        onchange: (value: string) => void;
        items: { value: string; text: string; label: string }[];
        label: string;
        class?: string;
    } = $props();
</script>

<ToggleGroupPrimitive.Root
    type="single"
    bind:value={
        () => value,
        (next) => {
            if (next) onchange(next);
        }
    }
    aria-label={label}
    class={cn(
        "flex border border-border-strong-01 in-dialog:border-border-strong-02",
        className,
    )}
>
    {#each items as item (item.value)}
        <ToggleGroupPrimitive.Item
            value={item.value}
            aria-label={item.label}
            class="flex h-6 min-w-6 cursor-pointer items-center justify-center px-1 text-label-01 text-text-secondary hover:bg-content-switcher-background-hover hover:text-text-primary data-[state=on]:bg-content-switcher-selected data-[state=on]:text-text-primary data-[state=on]:shadow-content-switcher-selected"
        >
            {item.text}
        </ToggleGroupPrimitive.Item>
    {/each}
</ToggleGroupPrimitive.Root>
