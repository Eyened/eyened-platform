<script lang="ts">
    import {
        Toaster as Sonner,
        type ToasterProps as SonnerProps,
    } from "svelte-sonner";

    let { ...restProps }: SonnerProps = $props();
</script>

<Sonner
    theme="dark"
    class="toaster group"
    style="--normal-bg: var(--color-layer-01); --normal-text: var(--color-text-primary); --normal-border: var(--color-border-subtle-01);"
    {...restProps}
/>
