<script lang="ts" module>
    // Carbon Tag (@carbon/styles 1.117.0 tag), gray, md.
    export const tagClasses =
        "inline-flex min-h-6 max-w-52 min-w-8 items-center rounded-tag bg-tag-background-gray px-2 text-label-01 text-tag-color-gray";
</script>

<script lang="ts">
    import type { Snippet } from "svelte";

    // Read-only: Carbon React's Tag without onClick or onClose is a plain, non-interactive element.
    let { children }: { children: Snippet } = $props();
</script>

<span data-slot="tag" class={tagClasses}>
    <span class="truncate">{@render children()}</span>
</span>
