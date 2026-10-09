<script lang="ts">
    import { Checkbox as CheckboxPrimitive } from "bits-ui";
    import { cn, type WithoutChildrenOrChild } from "$lib/utils.js";

    let {
        ref = $bindable(null),
        checked = $bindable(false),
        indeterminate = $bindable(false),
        class: className,
        ...restProps
    }: WithoutChildrenOrChild<CheckboxPrimitive.RootProps> = $props();
</script>

<!-- Carbon checkbox; values from @carbon/styles checkbox. Focus ring in app.css. -->
<CheckboxPrimitive.Root
    bind:ref
    data-slot="checkbox"
    class={cn(
        "peer flex size-4 shrink-0 items-center justify-center rounded-checkbox border border-icon-primary bg-transparent text-icon-inverse data-[state=checked]:bg-icon-primary data-[state=indeterminate]:bg-icon-primary",
        className,
    )}
    bind:checked
    bind:indeterminate
    {...restProps}
>
    {#snippet children({ checked, indeterminate })}
        {#if checked}
            <svg
                data-slot="checkbox-indicator"
                viewBox="0 0 14 14"
                class="size-full"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                aria-hidden="true"><path d="M3 7l3 3 5-6" /></svg
            >
        {:else if indeterminate}
            <svg
                data-slot="checkbox-indicator"
                viewBox="0 0 14 14"
                class="size-full"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                aria-hidden="true"><path d="M3 7h8" /></svg
            >
        {/if}
    {/snippet}
</CheckboxPrimitive.Root>
