<script lang="ts">
    import type { CarbonIconProps } from "carbon-icons-svelte";
    import type { Component } from "svelte";

    // Carbon status indicator pattern: icon + label, colour on the icon only.
    let {
        icon: Icon,
        iconClass,
        label,
    }: {
        icon: Component<CarbonIconProps>;
        iconClass: string;
        label: string;
    } = $props();
</script>

<span
    class="inline-flex items-center gap-2 text-body-compact-01 whitespace-nowrap text-text-primary"
>
    <Icon aria-hidden="true" class={iconClass} />
    {label}
</span>
