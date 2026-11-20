<script lang="ts">
    import { Label } from "$lib/components/ui/label/index.js";
    import * as Select from "$lib/components/ui/select/index.js";
    import { cn } from "$lib/utils.js";
    import { Combobox } from "bits-ui";
    import ChevronDown from "carbon-icons-svelte/lib/ChevronDown.svelte";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import { flushSync, tick } from "svelte";

    // Carbon ComboBox, md (40 px); values from @carbon/styles 1.117.0 list-box and combo-box, strings from
    // @carbon/react 1.118.0. The caller filters `items` by the typed `value`.
    // With `onselect`, a pick is an action: it calls `onselect` and empties the field. Without it, the pick is
    // kept in `selected` and stays shown; typing or ✕ clears it, and the parent clears the field by emptying both.
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        items,
        titleText,
        helperText,
        value = $bindable(""),
        selected = $bindable(""),
        id = uid,
        onselect,
    }: {
        items: { id: string; text: string }[];
        titleText: string;
        helperText?: string;
        value?: string;
        /** The picked id when there is no `onselect`; "" for none. */
        selected?: string;
        id?: string;
        onselect?: (id: string) => void;
    } = $props();

    let open = $state(false);
    // No match shows no list, not an empty panel.
    const listOpen = $derived(open && items.length > 0);
    let input = $state<HTMLInputElement | null>(null);
    const helperId = $derived(`${id}-helper`);

    async function pick(v: string) {
        if (!v) return;
        if (!onselect) {
            value = items.find((i) => i.id === v)?.text ?? "";
            return;
        }
        onselect(v);
        selected = "";
        value = "";
        // bits-ui writes the picked label into the input; clear it after that.
        await tick();
        if (input) input.value = "";
    }

    // Carbon: Esc clears the field. bits-ui only closes an open list, so with the list closed we clear,
    // and stop the event before the popover's or modal's escape layer on the document closes it.
    function onkeydown(e: KeyboardEvent) {
        if (e.key !== "Escape" || listOpen || !value) return;
        e.stopPropagation();
        value = "";
        selected = "";
    }
</script>

<div class="flex flex-col gap-2">
    <Label for={id}>{titleText}</Label>
    <Combobox.Root
        type="single"
        bind:open={() => listOpen, (v) => (open = v)}
        bind:value={selected}
        allowDeselect={false}
        inputValue={value}
        items={items.map((i) => ({ value: i.id, label: i.text }))}
        onValueChange={pick}
    >
        <div class="relative">
            <Combobox.Input
                bind:ref={input}
                {id}
                aria-describedby={helperText ? helperId : undefined}
                {onkeydown}
                oninput={(e) => {
                    value = e.currentTarget.value;
                    selected = "";
                    open = true;
                    flushSync(); // render the filtered list before bits-ui highlights its first option
                }}
                class={cn(
                    "h-10 w-full border-0 border-b border-border-strong-01 bg-field-01 ps-4 text-body-compact-01 text-text-primary placeholder:text-text-placeholder hover:bg-field-hover-01 in-dialog:border-border-strong-02 in-dialog:bg-field-02 in-dialog:hover:bg-field-hover-02",
                    value ? "pe-17.5" : "pe-12",
                )}
            />
            {#if value}
                <button
                    type="button"
                    tabindex="-1"
                    aria-label="Clear selected item"
                    title="Clear selected item"
                    class="absolute end-11.25 top-1/2 flex size-6 -translate-y-1/2 cursor-pointer items-center justify-center text-icon-primary"
                    onclick={() => {
                        value = "";
                        selected = "";
                        input?.focus();
                    }}
                >
                    <Close aria-hidden="true" />
                </button>
            {/if}
            <Combobox.Trigger
                tabindex={-1}
                aria-label={listOpen ? "Close" : "Open"}
                title={listOpen ? "Close" : "Open"}
                class="absolute end-3 top-1/2 flex size-6 -translate-y-1/2 cursor-pointer items-center justify-center text-icon-primary"
            >
                <ChevronDown
                    aria-hidden="true"
                    class={cn("transition-transform", listOpen && "rotate-180")}
                />
            </Combobox.Trigger>
        </div>
        <Select.Content class="max-h-55 w-(--bits-combobox-anchor-width)">
            {#each items as item (item.id)}
                <!-- The item truncates a long name, so the tooltip gives it in full. -->
                <Select.Item
                    value={item.id}
                    label={item.text}
                    title={item.text}
                    class="h-10"
                />
            {/each}
        </Select.Content>
    </Combobox.Root>
    {#if helperText}
        <p id={helperId} class="text-helper-text-01 text-text-helper">
            {helperText}
        </p>
    {/if}
</div>
