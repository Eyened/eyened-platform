<script lang="ts">
    import { cn, type WithElementRef } from "$lib/utils.js";
    import ChevronDown from "carbon-icons-svelte/lib/ChevronDown.svelte";
    import type { HTMLSelectAttributes } from "svelte/elements";

    let {
        ref = $bindable(null),
        value = $bindable(),
        class: className,
        children,
        ...restProps
    }: WithElementRef<HTMLSelectAttributes> = $props();
</script>

<!-- Carbon Select is a native <select>; values from @carbon/styles 1.117.0 select/_select.scss. -->
<div
    data-slot="native-select-wrapper"
    class="relative flex w-full items-center"
>
    <select
        bind:value
        bind:this={ref}
        data-slot="native-select"
        class={cn(
            "peer block h-10 w-full cursor-pointer appearance-none border-0 border-b border-border-strong-01 bg-field-01 py-0 pr-12 pl-4 text-body-compact-01 text-ellipsis text-text-primary hover:bg-field-hover-01 focus:outline-2 focus:-outline-offset-2 focus:outline-focus disabled:cursor-not-allowed disabled:border-transparent disabled:text-text-disabled in-dialog:border-border-strong-02 in-dialog:bg-field-02 in-dialog:hover:bg-field-hover-02",
            className,
        )}
        {...restProps}
    >
        {@render children?.()}
    </select>
    <ChevronDown
        aria-hidden="true"
        class="pointer-events-none absolute top-1/2 right-4 -translate-y-1/2 text-icon-primary peer-disabled:text-icon-disabled"
    />
</div>
