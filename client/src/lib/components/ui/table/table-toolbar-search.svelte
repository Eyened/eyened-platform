<script lang="ts">
    import { Label } from "$lib/components/ui/label/index.js";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import Search from "carbon-icons-svelte/lib/Search.svelte";

    // Carbon persistent toolbar search (carbon-components-svelte ToolbarSearch); values from
    // @carbon/styles 1.117.0 search/_search.scss and data-table/action. Esc clears, as Carbon does.
    const uid = $props.id(); // $props.id() is not allowed as a destructuring default
    let {
        labelText,
        placeholder,
        id = uid,
        value = $bindable(""),
    }: {
        labelText: string;
        placeholder?: string;
        id?: string;
        value?: string;
    } = $props();

    let input = $state<HTMLInputElement | null>(null);

    function clear() {
        value = "";
        input?.focus();
    }
</script>

<div
    role="search"
    class="relative flex h-12 min-w-0 flex-1 basis-40 items-center"
>
    <Label for={id} class="sr-only">{labelText}</Label>
    <Search
        aria-hidden="true"
        class="pointer-events-none absolute top-1/2 left-4 z-2 -translate-y-1/2 text-icon-secondary"
    />
    <input
        bind:this={input}
        bind:value
        {id}
        {placeholder}
        type="text"
        role="searchbox"
        autocomplete="off"
        class="h-12 w-full border-0 bg-field-01 px-12 text-body-compact-01 text-ellipsis text-text-primary not-placeholder-shown:bg-field-hover-01 placeholder:text-text-placeholder hover:bg-field-hover-01"
        onkeydown={(e) => {
            if (e.key === "Escape") clear();
        }}
    />
    {#if value}
        <button
            type="button"
            aria-label="Clear search input"
            class="absolute top-0 right-0 flex size-12 items-center justify-center text-icon-primary hover:bg-field-hover-01 active:bg-background-selected"
            onclick={clear}
        >
            <Close />
        </button>
    {/if}
</div>
