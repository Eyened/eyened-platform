<script lang="ts">
    import { cn } from "$lib/utils.js";
    import { Dialog as DialogPrimitive } from "bits-ui";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import type { Snippet } from "svelte";

    // IBM Products SidePanel (@carbon/ibm-products 2.99.0, styles 2.95.0), slide-over with an overlay.
    // bits-ui Dialog gives the focus trap, Escape (topmost layer only) and focus return. Rendered in
    // place: inside a modal its translated box is the containing block, so the panel stays in the modal.
    let {
        open = $bindable(false),
        title,
        subtitle,
        id,
        onCloseAutoFocus,
        children,
    }: {
        open?: boolean;
        title: string;
        subtitle?: string;
        id?: string;
        onCloseAutoFocus?: (event: Event) => void;
        children: Snippet;
    } = $props();
</script>

<DialogPrimitive.Root bind:open>
    <DialogPrimitive.Portal disabled>
        <DialogPrimitive.Overlay
            class="fixed inset-0 z-50 bg-overlay duration-150 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0"
        />
        <DialogPrimitive.Content
            {id}
            {onCloseAutoFocus}
            class="fixed top-12 right-0 bottom-0 z-50 flex w-120 max-w-full min-w-64 flex-col border-s border-border-subtle-01 bg-layer-01 text-text-primary duration-150 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:slide-out-to-right-80 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:slide-in-from-right-80 md:max-w-3/4 in-dialog:top-0 in-dialog:border-border-subtle-02 in-dialog:bg-layer-02"
        >
            <header
                class="relative border-b border-border-subtle-01 px-4 pt-4 in-dialog:border-border-subtle-02"
            >
                <DialogPrimitive.Title
                    class={cn(
                        "pe-8 text-heading-03",
                        subtitle ? "pb-2" : "pb-4",
                    )}
                >
                    {title}
                </DialogPrimitive.Title>
                {#if subtitle}
                    <p class="pb-4 text-body-compact-01">{subtitle}</p>
                {/if}
                <DialogPrimitive.Close
                    aria-label="Close"
                    class="absolute top-4 right-4 flex size-8 cursor-pointer items-center justify-center text-icon-primary hover:bg-background-hover"
                >
                    <Close aria-hidden="true" />
                </DialogPrimitive.Close>
            </header>
            <div class="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
                {@render children()}
            </div>
        </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
</DialogPrimitive.Root>
