<script lang="ts">
    import { Label } from "$lib/components/ui/label/index.js";
    import { cn } from "$lib/utils.js";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import SearchIcon from "carbon-icons-svelte/lib/Search.svelte";

    // Carbon Search (carbon-components-svelte Search), lg 48 px or md 40 px; values from @carbon/styles 1.117.0 search/_search.scss.
    // Esc clears the text, as Carbon does, and stops there; with nothing to clear it passes on, so a panel or dialog can take it.
    const uid = $props.id();
    let {
        labelText,
        placeholder,
        id = uid,
        value = $bindable(""),
        size = "lg",
        class: className,
    }: {
        labelText: string;
        placeholder?: string;
        id?: string;
        value?: string;
        size?: "lg" | "md";
        class?: string;
    } = $props();

    let input = $state<HTMLInputElement | null>(null);
    const height = $derived(size === "lg" ? "h-12" : "h-10");

    function clear() {
        value = "";
        input?.focus();
    }

    function onkeydown(e: KeyboardEvent) {
        if (e.key !== "Escape" || !value) return;
        e.preventDefault();
        e.stopPropagation();
        clear();
    }
</script>

<div
    role="search"
    class={cn("relative flex min-w-0 items-center", height, className)}
>
    <Label for={id} class="sr-only">{labelText}</Label>
    <SearchIcon
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
        class={cn(
            "w-full border-0 border-b border-border-strong-01 bg-field-01 px-12 text-body-compact-01 text-ellipsis text-text-primary placeholder:text-text-placeholder hover:bg-field-hover-01 in-dialog:border-border-strong-02 in-dialog:bg-field-02 in-dialog:hover:bg-field-hover-02",
            height,
        )}
        {onkeydown}
    />
    {#if value}
        <button
            type="button"
            aria-label="Clear search input"
            class={cn(
                "absolute top-0 right-0 flex items-center justify-center text-icon-primary hover:bg-field-hover-01 active:bg-background-selected",
                size === "lg" ? "size-12" : "size-10",
            )}
            onclick={clear}
        >
            <Close />
        </button>
    {/if}
</div>
