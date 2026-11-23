<script lang="ts" module>
    // Carbon Tag (@carbon/styles 1.117.0 tag), gray or red, md.
    const base =
        "inline-flex min-h-6 max-w-52 min-w-8 items-center rounded-tag px-2 text-label-01";
    export const tagClasses = `${base} bg-tag-background-gray text-tag-color-gray`;
    const redTagClasses = `${base} bg-tag-background-red text-tag-color-red`;
</script>

<script lang="ts">
    import type { Snippet } from "svelte";

    // Read-only: Carbon React's Tag without onClick or onClose is a plain, non-interactive element.
    let {
        children,
        type = "gray",
    }: { children: Snippet; type?: "gray" | "red" } = $props();
</script>

<span data-slot="tag" class={type === "red" ? redTagClasses : tagClasses}>
    <span class="truncate">{@render children()}</span>
</span>
