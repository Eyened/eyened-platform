<script lang="ts">
    import * as Dialog from "$lib/components/ui/dialog/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { modalSizeClasses } from "$lib/components/ui/modal/sizes.js";
    import { getThumbUrl } from "$lib/data-loading/utils";
    import { cn } from "$lib/utils.js";
    import { copyToClipboard } from "$lib/utils/copyToClipboard";
    import Checkbox from "carbon-icons-svelte/lib/Checkbox.svelte";
    import CheckboxCheckedFilled from "carbon-icons-svelte/lib/CheckboxCheckedFilled.svelte";
    import Copy from "carbon-icons-svelte/lib/Copy.svelte";
    import Information from "carbon-icons-svelte/lib/Information.svelte";
    import { getContext } from "svelte";
    import type { ImageGET } from "../../types/openapi_types";
    import type { BrowserContext } from "./browserContext.svelte";
    import { instanceLabel } from "./images";
    import InstanceInfoLazy from "./InstanceInfoLazy.svelte";

    // A selectable image item: the whole item toggles the selection, the checkbox sits over the
    // image's top-left corner, and the image-info button is its own click target.
    const browserContext = getContext<BrowserContext>("browserContext");

    interface Props {
        instance: ImageGET;
        // false: no checkbox and no toggle (task page thumbnails).
        selectable?: boolean;
    }
    let { instance, selectable = true }: Props = $props();

    let infoOpen = $state(false);
    let copied = $state(false);
    const label = $derived(instanceLabel(instance));
    const size = $derived(browserContext.thumbnailSize);
    const selected = $derived(
        selectable && browserContext.selectedIds.includes(instance.id),
    );

    function onkeydown(e: KeyboardEvent) {
        if (e.key !== "Enter" && e.key !== " ") return;
        e.preventDefault();
        browserContext.toggleInstance(instance);
    }

    // Carbon CopyButton feedback: "Copied!" for 2 s.
    async function copy() {
        copied = await copyToClipboard(instance.id);
        setTimeout(() => (copied = false), 2000);
    }
</script>

<div
    class={cn(
        "relative flex flex-col border border-transparent bg-layer-01 in-dialog:bg-layer-02 in-study:bg-layer-02 in-dialog:in-study:bg-layer-03",
        selectable &&
            "hover:bg-layer-hover-01 in-dialog:hover:bg-layer-hover-02 in-study:hover:bg-layer-hover-02 in-dialog:in-study:hover:bg-layer-hover-03",
        selected && "border-layer-selected-inverse",
    )}
>
    {#if selectable}
        <div
            role="checkbox"
            aria-checked={selected}
            aria-label="{label} {instance.id}"
            tabindex="0"
            class="absolute inset-0 cursor-pointer"
            onclick={() => browserContext.toggleInstance(instance)}
            {onkeydown}
        ></div>
    {/if}
    <!-- Empty item area until the image loads. -->
    <img
        src={getThumbUrl(instance)}
        alt=""
        loading="lazy"
        draggable="false"
        class="pointer-events-none object-contain"
        style="width: {size}; height: {size};"
    />
    {#if selectable}
        <!-- A backing keeps the checkbox readable on bright images. -->
        <span
            class="pointer-events-none absolute top-2 left-2 flex bg-layer-01 p-0.5 in-dialog:bg-layer-02 in-study:bg-layer-02 in-dialog:in-study:bg-layer-03"
        >
            {#if selected}
                <CheckboxCheckedFilled
                    aria-hidden="true"
                    class="text-icon-primary"
                />
            {:else}
                <Checkbox aria-hidden="true" class="text-icon-secondary" />
            {/if}
        </span>
    {/if}
    <div
        class="flex items-center justify-between gap-2 py-1 ps-2 pe-1"
        style="width: {size};"
    >
        <span
            class="pointer-events-none truncate text-label-01 text-text-secondary"
        >
            {label}
        </span>
        <IconButton
            label="Image information"
            class="size-6"
            onclick={() => (infoOpen = true)}
        >
            <Information />
        </IconButton>
    </div>
</div>

<!-- Carbon Modal lg, passive: no footer, ✕ only; an outside click closes it. -->
<Dialog.Root bind:open={infoOpen}>
    <Dialog.Content class={cn("gap-0 p-0", modalSizeClasses.lg)}>
        <Dialog.Header class="mb-2 pt-4 pr-12 pl-4">
            <p class="text-label-01 text-text-secondary">Image</p>
            <div class="flex min-w-0 items-center gap-2">
                <Dialog.Title class="truncate">{instance.id}</Dialog.Title>
                <IconButton
                    label={copied ? "Copied!" : "Copy public ID"}
                    onclick={copy}
                >
                    <Copy />
                </IconButton>
            </div>
        </Dialog.Header>
        <div
            class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 pt-2 pb-12 md:overflow-hidden"
        >
            <InstanceInfoLazy instanceId={instance.id} />
        </div>
    </Dialog.Content>
</Dialog.Root>
