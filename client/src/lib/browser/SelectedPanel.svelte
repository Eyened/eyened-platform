<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { SidePanel } from "$lib/components/ui/side-panel/index.js";
    import { getThumbUrl } from "$lib/data-loading/utils";
    import Subtract from "carbon-icons-svelte/lib/Subtract.svelte";
    import { getContext, tick } from "svelte";
    import type { ImageGET } from "../../types/openapi_types";
    import type { BrowserContext } from "./browserContext.svelte";
    import { eyeName, imageCount, instanceLabel } from "./images";

    let {
        open = $bindable(false),
        onCloseAutoFocus,
    }: { open?: boolean; onCloseAutoFocus?: (event: Event) => void } = $props();

    const browserContext = getContext<BrowserContext>("browserContext");
    let list = $state<HTMLUListElement>();

    // Focus moves to the next row's Remove, or the previous row's after the last one. Removing the
    // only row closes the panel, and the Browser moves focus to Filters.
    async function remove(instance: ImageGET, index: number) {
        const remaining = browserContext.selectedIds.length - 1;
        browserContext.toggleInstance(instance);
        if (remaining === 0) return;
        await tick();
        list?.querySelectorAll<HTMLButtonElement>("li button")[
            Math.min(index, remaining - 1)
        ]?.focus();
    }
</script>

<SidePanel
    bind:open
    id="selected-images"
    title="Selected images"
    subtitle={imageCount(browserContext.selectedIds.length)}
    {onCloseAutoFocus}
>
    <ul bind:this={list}>
        {#each browserContext.selectedInstances as instance, index (instance.id)}
            {@const label = instanceLabel(instance)}
            <li
                class="flex items-center gap-4 border-b border-border-subtle-01 py-2 in-dialog:border-border-subtle-02"
            >
                <img
                    src={getThumbUrl(instance)}
                    alt=""
                    class="size-12 shrink-0 object-contain"
                />
                <div class="min-w-0 flex-1">
                    <p class="truncate text-body-compact-01">
                        {label} · {eyeName(instance.laterality ?? null)}
                    </p>
                    <p class="truncate text-label-01 text-text-secondary">
                        {instance.patient.identifier} · {instance.study.date}
                    </p>
                </div>
                <IconButton
                    label="Remove {label || 'image'} from selection"
                    onclick={() => remove(instance, index)}
                >
                    <Subtract />
                </IconButton>
            </li>
        {/each}
    </ul>
</SidePanel>
