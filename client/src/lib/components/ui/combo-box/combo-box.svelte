<script lang="ts">
    import { Label } from "$lib/components/ui/label/index.js";
    import * as Select from "$lib/components/ui/select/index.js";
    import { cn } from "$lib/utils.js";
    import { Combobox } from "bits-ui";
    import ChevronDown from "carbon-icons-svelte/lib/ChevronDown.svelte";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import { tick } from "svelte";

    // Carbon ComboBox, md (40 px); values from @carbon/styles 1.117.0 list-box and combo-box, strings from
    // @carbon/react 1.118.0. The caller filters `items` by the typed `value`. A pick is an action, not a
    // stored value: it calls `onselect` and empties the field.
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        items,
        titleText,
        value = $bindable(""),
        id = uid,
        onselect,
    }: {
        items: { id: string; text: string }[];
        titleText: string;
        value?: string;
        id?: string;
        onselect: (id: string) => void;
    } = $props();

    let open = $state(false);
    let picked = $state("");
    let input = $state<HTMLInputElement | null>(null);

    async function pick(v: string) {
        if (!v) return;
        onselect(v);
        picked = "";
        value = "";
        // bits-ui writes the picked label into the input; clear it after that.
        await tick();
        if (input) input.value = "";
    }
</script>

<div class="flex flex-col gap-2">
    <Label for={id}>{titleText}</Label>
    <Combobox.Root
        type="single"
        bind:open
        bind:value={picked}
        inputValue={value}
        items={items.map((i) => ({ value: i.id, label: i.text }))}
        onValueChange={pick}
    >
        <div class="relative">
            <Combobox.Input
                bind:ref={input}
                {id}
                oninput={(e) => {
                    value = e.currentTarget.value;
                    open = true;
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
                        input?.focus();
                    }}
                >
                    <Close aria-hidden="true" />
                </button>
            {/if}
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
            {#each items as item (item.id)}
                <Select.Item value={item.id} label={item.text} class="h-10" />
            {/each}
        </Select.Content>
    </Combobox.Root>
</div>
