<script lang="ts">
    import { Dialog as DialogPrimitive } from "bits-ui";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import type { Snippet } from "svelte";
    import * as Dialog from "./index.js";
    import { cn, type WithoutChildrenOrChild } from "$lib/utils.js";

    let {
        ref = $bindable(null),
        class: className,
        portalProps,
        children,
        showCloseButton = true,
        ...restProps
    }: WithoutChildrenOrChild<DialogPrimitive.ContentProps> & {
        portalProps?: DialogPrimitive.PortalProps;
        children: Snippet;
        showCloseButton?: boolean;
    } = $props();
</script>

<Dialog.Portal {...portalProps}>
    <Dialog.Overlay />
    <DialogPrimitive.Content
        bind:ref
        data-slot="dialog-content"
        class={cn(
            "fixed top-0 left-0 z-50 flex max-h-full w-full flex-col gap-4 border border-border-subtle-01 bg-layer-01 p-4 text-text-primary duration-240 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0 md:top-1/2 md:left-1/2 md:max-h-9/10 md:w-21/25 md:-translate-x-1/2 md:-translate-y-1/2 lg:max-h-21/25 lg:w-3/5 xlg:w-12/25",
            className,
        )}
        {...restProps}
    >
        {@render children?.()}
        {#if showCloseButton}
            <DialogPrimitive.Close
                aria-label="Close"
                class="absolute top-0 right-0 flex size-12 items-center justify-center border-2 border-transparent hover:bg-layer-hover-01"
            >
                <Close size={20} class="text-icon-primary" />
            </DialogPrimitive.Close>
        {/if}
    </DialogPrimitive.Content>
</Dialog.Portal>
