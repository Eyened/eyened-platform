<script lang="ts">
    import type { WithElementRef } from "$lib/utils.js";
    import type { HTMLAttributes } from "svelte/elements";

    // Carbon Breadcrumb; values from @carbon/styles 1.117.0 breadcrumb. The current page is not listed.
    let {
        ref = $bindable(null),
        class: className,
        children,
        ...restProps
    }: WithElementRef<HTMLAttributes<HTMLElement>> = $props();
</script>

<nav
    bind:this={ref}
    data-slot="breadcrumb"
    class={className}
    aria-label="Breadcrumb"
    {...restProps}
>
    {@render children?.()}
</nav>
