<script lang="ts" module>
    // Carbon Tag (@carbon/styles 1.117.0 tag), gray, red, blue or green, md; an optional 16 px icon 4 px before the text.
    const base =
        "inline-flex min-h-6 max-w-52 min-w-8 items-center rounded-tag px-2 text-label-01";
    export const tagClasses = `${base} bg-tag-background-gray text-tag-color-gray`;
    const typeClasses = {
        gray: tagClasses,
        red: `${base} bg-tag-background-red text-tag-color-red`,
        blue: `${base} bg-tag-background-blue text-tag-color-blue`,
        green: `${base} bg-tag-background-green text-tag-color-green`,
    };
</script>

<script lang="ts">
    import { cn } from "$lib/utils.js";
    import type { CarbonIconProps } from "carbon-icons-svelte";
    import type { Component, Snippet } from "svelte";

    // Read-only: Carbon React's Tag without onClick or onClose is a plain, non-interactive element.
    let {
        children,
        type = "gray",
        icon: Icon,
        class: className,
        title,
    }: {
        children: Snippet;
        type?: keyof typeof typeClasses;
        /** Carbon's renderIcon; decorative, the text names the tag. */
        icon?: Component<CarbonIconProps>;
        class?: string;
        /** The full text on hover, when the tag may cut it. */
        title?: string;
    } = $props();
</script>

<span
    data-slot="tag"
    {title}
    class={cn(typeClasses[type], Icon && "ps-1", className)}
>
    {#if Icon}
        <Icon aria-hidden="true" class="me-1 shrink-0" />
    {/if}
    <span class="truncate">{@render children()}</span>
</span>
