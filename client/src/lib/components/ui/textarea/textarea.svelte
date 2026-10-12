<script lang="ts">
    import {
        cn,
        type WithElementRef,
        type WithoutChildren,
    } from "$lib/utils.js";
    import type { HTMLTextareaAttributes } from "svelte/elements";

    let {
        ref = $bindable(null),
        value = $bindable(),
        class: className,
        ...restProps
    }: WithoutChildren<WithElementRef<HTMLTextareaAttributes>> = $props();
</script>

<!-- Carbon text area; values from @carbon/styles 1.117.0 text-area/_text-area.scss. -->
<textarea
    bind:this={ref}
    data-slot="textarea"
    class={cn(
        "block min-h-10 w-full min-w-40 resize-y border-0 border-b border-border-strong-01 bg-field-01 px-4 pt-2.75 pb-2 text-body-01 text-text-primary placeholder:text-text-placeholder disabled:cursor-not-allowed disabled:resize-none disabled:border-transparent disabled:text-text-disabled in-dialog:border-border-strong-02 in-dialog:bg-field-02",
        className,
    )}
    bind:value
    {...restProps}
></textarea>
