<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { SidePanel } from "$lib/components/ui/side-panel/index.js";
    import { getThumbUrl } from "$lib/data-loading/utils";
    import Subtract from "carbon-icons-svelte/lib/Subtract.svelte";
    import { getContext } from "svelte";
    import type { BrowserContext } from "./browserContext.svelte";
    import { eyeName, imageCount, instanceLabel } from "./images";

    let {
        open = $bindable(false),
        onCloseAutoFocus,
    }: { open?: boolean; onCloseAutoFocus?: (event: Event) => void } = $props();

    const browserContext = getContext<BrowserContext>("browserContext");
</script>

<SidePanel
    bind:open
    id="selected-images"
    title="Selected images"
    subtitle={imageCount(browserContext.selectedIds.length)}
    {onCloseAutoFocus}
>
    <ul>
        {#each browserContext.selectedInstances as instance (instance.id)}
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
                    onclick={() => browserContext.toggleInstance(instance)}
                >
                    <Subtract />
                </IconButton>
            </li>
        {/each}
    </ul>
</SidePanel>
