<script lang="ts">
    import { mergeProps, ToggleGroup as ToggleGroupPrimitive } from "bits-ui";
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import { cn } from "$lib/utils.js";

    // Single-select toggle group (Carbon has none): one Tab stop on the selected option, arrow keys inside.
    // No item is selected when `value` matches none; pressing the selected item keeps it selected.
    // In a narrow column a label with a tooltip truncates; one without keeps its full text.
    let {
        value,
        onchange,
        items,
        label,
        describedby,
        class: className,
    }: {
        value: string;
        onchange: (value: string) => void;
        items: {
            value: string;
            text: string;
            label: string;
            tooltip?: string;
        }[];
        label: string;
        /** The id of the element that describes the group. */
        describedby?: string;
        class?: string;
    } = $props();

    // bits-ui moves its Tab stop only on click or arrow, so a value set in code would leave it behind.
    // Inside the group the focused option holds the stop, so Tab leaves the group from any option.
    let focused = $state<string | null>(null);
    const tabStop = $derived(
        focused ??
            (items.some((item) => item.value === value)
                ? value
                : items[0]?.value),
    );
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
    aria-describedby={describedby}
    onfocusout={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null))
            focused = null;
    }}
    class={cn(
        "flex border border-border-strong-01 in-dialog:border-border-strong-02",
        className,
    )}
>
    {#each items as item (item.value)}
        <ToggleGroupPrimitive.Item
            value={item.value}
            aria-label={item.label}
            class="{item.tooltip
                ? ''
                : 'shrink-0'} flex h-6 min-w-6 cursor-pointer items-center justify-center px-1 text-label-01 text-text-secondary hover:bg-content-switcher-background-hover hover:text-text-primary data-[state=on]:bg-content-switcher-selected data-[state=on]:text-text-primary data-[state=on]:shadow-content-switcher-selected"
        >
            {#snippet child({ props })}
                {#if item.tooltip}
                    <!-- A short label carries its full name as a tooltip, on hover and on focus. -->
                    <Tooltip.Provider delayDuration={100}>
                        <Tooltip.Root>
                            <Tooltip.Trigger>
                                {#snippet child({ props: tip })}
                                    <button
                                        {...mergeProps(tip, props, {
                                            onfocus: () =>
                                                (focused = item.value),
                                        })}
                                        tabindex={item.value === tabStop
                                            ? 0
                                            : -1}
                                    >
                                        <span class="min-w-0 truncate"
                                            >{item.text}</span
                                        >
                                    </button>
                                {/snippet}
                            </Tooltip.Trigger>
                            <Tooltip.Content>{item.tooltip}</Tooltip.Content>
                        </Tooltip.Root>
                    </Tooltip.Provider>
                {:else}
                    <button
                        {...props}
                        tabindex={item.value === tabStop ? 0 : -1}
                        onfocus={() => (focused = item.value)}
                    >
                        <span class="min-w-0 truncate">{item.text}</span>
                    </button>
                {/if}
            {/snippet}
        </ToggleGroupPrimitive.Item>
    {/each}
</ToggleGroupPrimitive.Root>
