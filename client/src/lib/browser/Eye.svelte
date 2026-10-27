<script lang="ts">
    import { resolve } from "$app/paths";
    import Launch from "carbon-icons-svelte/lib/Launch.svelte";
    import type { ImageGET } from "../../types/openapi_types";
    import { eyeName, type Laterality } from "./images";
    import InstanceComponent from "./InstanceComponent.svelte";

    let { laterality, images }: { laterality: Laterality; images: ImageGET[] } =
        $props();

    const name = $derived(eyeName(laterality));
    const linkText = $derived(
        laterality
            ? `Open all ${name} images`
            : "Open all images with unknown laterality",
    );
    const href = $derived(
        `${resolve("/view")}?instances=${images.map((i) => i.id).join(",")}`,
    );
</script>

<!-- Columns are split by border-subtle lines (Carbon's dividers); they stack below md. -->
<div
    class="flex min-w-0 flex-1 flex-col gap-4 not-first:border-border-subtle-01 max-md:py-4 max-md:not-first:border-t max-md:first:pt-0 md:px-4 md:not-first:border-s md:first:ps-0 md:last:pe-0 in-dialog:not-first:border-border-subtle-02"
>
    <h3 class="text-heading-compact-01">{name}</h3>
    {#if images.length > 0}
        <div class="flex flex-wrap gap-2">
            {#each images as instance (instance.id)}
                <InstanceComponent {instance} />
            {/each}
        </div>
        <!-- Carbon standalone Link with Launch (opens another tab); a link, not a button (D8). -->
        <!-- eslint-disable svelte/no-navigation-without-resolve -- href is resolve("/view") plus a query string -->
        <a
            {href}
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-2 self-start text-body-compact-01 text-link-primary hover:text-link-primary-hover hover:underline"
        >
            {linkText}
            <Launch aria-hidden="true" />
        </a>
        <!-- eslint-enable svelte/no-navigation-without-resolve -->
    {:else}
        <p class="text-body-01 text-text-secondary">No images for this eye</p>
    {/if}
</div>
