<script lang="ts">
    import * as Command from "$lib/components/ui/command/index.js";
    import Checkbox from "carbon-icons-svelte/lib/Checkbox.svelte";
    import CheckboxCheckedFilled from "carbon-icons-svelte/lib/CheckboxCheckedFilled.svelte";
    import Checkmark from "carbon-icons-svelte/lib/Checkmark.svelte";
    import { untrack } from "svelte";

    // IBM Products ConditionBuilder ItemOption on ui/command: a search field above 4 options
    // (popOverSearchThreshold); single (a pick closes the popover; the choice has a checkmark) or
    // multi (checkboxes; stays open). Values from @carbon/ibm-products-styles 2.95.0.
    const SEARCH_THRESHOLD = 4;

    let {
        options,
        selected,
        multi = false,
        label,
        searchLabel = "Search properties",
        onselect,
    }: {
        options: { id: string; label: string }[];
        selected: string[];
        multi?: boolean;
        /** The list's accessible name. */
        label: string;
        searchLabel?: string;
        onselect: (id: string) => void;
    } = $props();

    let root = $state<HTMLElement | null>(null);
    // bits-ui Command's value is the highlighted option; start on the current choice (read once).
    let highlighted = $state(untrack(() => selected[0] ?? ""));

    // Space toggles the highlighted option of a multi list (Enter is Command's); in the search field it types.
    function onkeydown(e: KeyboardEvent) {
        if (!multi || e.key !== " " || e.target instanceof HTMLInputElement)
            return;
        e.preventDefault();
        root?.querySelector<HTMLElement>(
            "[data-slot='command-item'][data-selected]",
        )?.click();
    }
</script>

<Command.Root bind:ref={root} bind:value={highlighted} {onkeydown}>
    {#if options.length > SEARCH_THRESHOLD}
        <div class="px-4 pb-4">
            <Command.Input aria-label={searchLabel} />
        </div>
    {/if}
    <Command.List
        aria-label={label}
        aria-multiselectable={multi || undefined}
        class="max-h-none"
    >
        {#each options as option (option.id)}
            {@const chosen = selected.includes(option.id)}
            <Command.Item
                value={option.id}
                keywords={[option.label]}
                aria-checked={chosen}
                onSelect={() => onselect(option.id)}
                class="group/option"
            >
                <span
                    class="flex min-h-8 w-full min-w-0 items-center gap-2 border-t border-border-subtle-01 group-hover/option:border-transparent group-aria-checked/option:border-transparent group-data-selected/option:border-transparent in-dialog:border-border-subtle-02 first-option:border-transparent after-active-option:border-transparent"
                >
                    {#if multi}
                        {#if chosen}
                            <CheckboxCheckedFilled aria-hidden="true" />
                        {:else}
                            <Checkbox aria-hidden="true" />
                        {/if}
                    {/if}
                    <span class="truncate" title={option.label}
                        >{option.label}</span
                    >
                    {#if !multi && chosen}
                        <Checkmark aria-hidden="true" class="ms-auto" />
                    {/if}
                </span>
            </Command.Item>
        {/each}
    </Command.List>
</Command.Root>
