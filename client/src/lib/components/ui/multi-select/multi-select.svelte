<script lang="ts">
    import { Label } from "$lib/components/ui/label/index.js";
    import * as Select from "$lib/components/ui/select/index.js";
    import { DismissibleTag } from "$lib/components/ui/tag/index.js";
    import { cn } from "$lib/utils.js";
    import { Combobox, Select as SelectPrimitive } from "bits-ui";
    import ChevronDown from "carbon-icons-svelte/lib/ChevronDown.svelte";
    import { flushSync, tick } from "svelte";

    // Carbon FilterableMultiSelect, md (40 px); field values as ui/combo-box, strings from Carbon React
    // MultiSelect. A pick toggles a stored value: the menu stays open and the typed filter stays.
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        titleText,
        options,
        values = $bindable([]),
        placeholder,
        helperText,
        id = uid,
    }: {
        titleText: string;
        options: { value: string; label: string }[];
        values?: string[];
        placeholder?: string;
        helperText?: string;
        id?: string;
    } = $props();

    let open = $state(false);
    let filter = $state("");
    let input = $state<HTMLInputElement | null>(null);

    const query = $derived(filter.trim().toLowerCase());
    const shown = $derived(
        query
            ? options.filter((o) => o.label.toLowerCase().includes(query))
            : options,
    );
    const helperId = $derived(`${id}-helper`);
    const selectionId = $derived(`${id}-selection`);
    const describedBy = $derived(
        [helperText ? helperId : "", values.length ? selectionId : ""]
            .filter(Boolean)
            .join(" ") || undefined,
    );

    // bits-ui writes the toggled label into the input; put the filter back after that.
    async function restoreFilter() {
        await tick();
        if (input) input.value = filter;
    }

    function clearAll() {
        values = [];
        filter = "";
        input?.focus();
    }

    function onkeydown(e: KeyboardEvent) {
        if (open || !values.length) return;
        if (e.key === "Delete" || (e.key === "Backspace" && !filter)) {
            e.preventDefault(); // stops bits-ui opening the menu
            clearAll();
        }
    }
</script>

<div class="flex flex-col gap-2">
    <Label for={id}>{titleText}</Label>
    <Combobox.Root
        type="multiple"
        bind:open
        bind:value={values}
        inputValue={filter}
        items={options}
        onValueChange={restoreFilter}
    >
        <div class="relative">
            {#if values.length}
                <span class="absolute start-2 top-1/2 z-1 -translate-y-1/2">
                    <DismissibleTag
                        text={String(values.length)}
                        title="Clear selection"
                        ondismiss={clearAll}
                    />
                </span>
                <span id={selectionId} class="sr-only">
                    Total items selected: {values.length}. To clear selection,
                    press Delete or Backspace.
                </span>
            {/if}
            <Combobox.Input
                bind:ref={input}
                {id}
                {placeholder}
                aria-describedby={describedBy}
                oninput={(e) => {
                    filter = e.currentTarget.value;
                    open = true;
                    flushSync(); // render the filtered list before bits-ui highlights its first option
                }}
                {onkeydown}
                class={cn(
                    "h-10 w-full border-0 border-b border-border-strong-01 bg-field-01 pe-12 text-body-compact-01 text-text-primary placeholder:text-text-placeholder hover:bg-field-hover-01 in-dialog:border-border-strong-02 in-dialog:bg-field-02 in-dialog:hover:bg-field-hover-02",
                    values.length ? "ps-16" : "ps-4",
                )}
            />
            <Combobox.Trigger
                tabindex={-1}
                aria-label={open ? "Close" : "Open"}
                title={open ? "Close" : "Open"}
                class="absolute end-3 top-1/2 flex size-6 -translate-y-1/2 cursor-pointer items-center justify-center text-icon-primary"
            >
                <ChevronDown
                    aria-hidden="true"
                    class={cn("transition-transform", open && "rotate-180")}
                />
            </Combobox.Trigger>
        </div>
        <Select.Content class="max-h-55 w-(--bits-combobox-anchor-width)">
            {#each shown as option (option.value)}
                <SelectPrimitive.Item
                    value={option.value}
                    label={option.label}
                    data-slot="select-item"
                    class="group/item relative h-10 cursor-pointer text-body-compact-01 text-text-secondary select-none hover:bg-layer-hover-01 hover:text-text-primary data-highlighted:text-text-primary data-highlighted:outline-2 data-highlighted:-outline-offset-2 data-highlighted:outline-focus data-selected:bg-layer-selected-01 data-selected:text-text-primary data-selected:hover:bg-layer-selected-hover-01"
                >
                    {#snippet children({ selected })}
                        <span
                            class="mx-4 flex h-full items-center gap-2 border-t border-border-subtle-01 group-first/item:border-transparent group-hover/item:border-transparent group-data-highlighted/item:border-transparent group-data-selected/item:border-transparent after-active-item:border-transparent"
                        >
                            <!-- Drawn like ui/checkbox; the option itself carries aria-selected. -->
                            <span
                                aria-hidden="true"
                                class={cn(
                                    "flex size-4 shrink-0 items-center justify-center rounded-checkbox border border-icon-primary text-icon-inverse",
                                    selected && "bg-icon-primary",
                                )}
                            >
                                {#if selected}
                                    <svg
                                        viewBox="0 0 14 14"
                                        class="size-full"
                                        fill="none"
                                        stroke="currentColor"
                                        stroke-width="1.5"
                                        ><path d="M3 7l3 3 5-6" /></svg
                                    >
                                {/if}
                            </span>
                            <span class="truncate">{option.label}</span>
                        </span>
                    {/snippet}
                </SelectPrimitive.Item>
            {/each}
        </Select.Content>
    </Combobox.Root>
    {#if helperText}
        <p id={helperId} class="text-helper-text-01 text-text-helper">
            {helperText}
        </p>
    {/if}
</div>
