<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Dialog from "$lib/components/ui/dialog/index.js";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { cn } from "$lib/utils.js";
    import type { Snippet } from "svelte";

    // Carbon transactional Modal over ui/dialog; prop names from carbon-components-svelte.
    // Values from @carbon/styles 1.117.0 modal/_modal.scss; loading flow from Carbon React Modal.tsx.
    type Props = {
        open?: boolean;
        modalHeading: string;
        modalLabel?: string;
        primaryButtonText: string;
        secondaryButtonText?: string;
        primaryButtonLoadingDescription: string;
        successDescription: string;
        errorTitle: string;
        danger?: boolean;
        size?: "xs" | "sm";
        /** Return false to stay idle (invalid input, nothing to save); reject to show the error. */
        onsubmit: () => false | Promise<unknown>;
        onCloseAutoFocus?: (event: Event) => void;
        children: Snippet;
    };

    let {
        open = $bindable(false),
        modalHeading,
        modalLabel,
        primaryButtonText,
        secondaryButtonText = "Cancel",
        primaryButtonLoadingDescription,
        successDescription,
        errorTitle,
        danger = false,
        size = "sm",
        onsubmit,
        onCloseAutoFocus,
        children,
    }: Props = $props();

    const SUCCESS_MS = 1500; // Carbon InlineLoading: the finished state shows for 1.5 s
    const footerButton = "h-16 max-w-none basis-1/2 items-start pt-3.5 pb-8";

    let status = $state<"inactive" | "active" | "finished">("inactive");
    let error = $state<string | null>(null);
    let primary = $state<HTMLElement | null>(null);
    let cancel = $state<HTMLElement | null>(null);
    const busy = $derived(status !== "inactive");

    // Every close path (Esc, the X, Cancel) comes through here, so none closes a busy modal.
    function setOpen(value: boolean) {
        if (busy) return;
        open = value;
        if (!value) error = null;
    }

    async function submit(event: SubmitEvent) {
        event.preventDefault();
        if (busy) return;
        const pending = onsubmit();
        if (pending === false) return;
        // A focused field that becomes disabled drops focus out of the modal; park it first.
        primary?.focus();
        error = null;
        status = "active";
        try {
            await pending;
        } catch (e) {
            status = "inactive";
            error = e instanceof Error ? e.message : String(e);
            return;
        }
        status = "finished";
        setTimeout(() => {
            status = "inactive";
            setOpen(false);
        }, SUCCESS_MS);
    }
</script>

<Dialog.Root bind:open={() => open, setOpen}>
    <Dialog.Content
        class={cn(
            "gap-0 p-0",
            // Carbon modal/_modal.scss: xs 48% / 32% / 24%, sm 60% / 42% / 36% at md / lg / xlg.
            size === "xs"
                ? "md:w-12/25 lg:max-h-12/25 lg:w-8/25 xlg:w-6/25"
                : "md:w-3/5 lg:max-h-18/25 lg:w-21/50 xlg:w-9/25",
        )}
        interactOutsideBehavior="ignore"
        onOpenAutoFocus={(e) => {
            // Carbon: a danger modal focuses Cancel; others their first field.
            if (danger) {
                e.preventDefault();
                cancel?.focus();
            }
        }}
        {onCloseAutoFocus}
    >
        <form class="flex min-h-0 flex-1 flex-col" novalidate onsubmit={submit}>
            <Dialog.Header class="mb-2 pt-4 pr-12 pl-4">
                {#if modalLabel}
                    <p class="text-label-01 text-text-secondary">
                        {modalLabel}
                    </p>
                {/if}
                <Dialog.Title>{modalHeading}</Dialog.Title>
            </Dialog.Header>
            <fieldset
                disabled={busy}
                class="min-h-0 min-w-0 flex-1 overflow-y-auto px-4 pt-2 pb-12 text-body-01 text-text-primary"
            >
                {@render children()}
                {#if error}
                    <InlineNotification
                        class="mt-6"
                        title={errorTitle}
                        subtitle={error}
                    />
                {/if}
            </fieldset>
            <div class="flex h-16">
                <Button
                    variant="secondary"
                    class={footerButton}
                    bind:ref={cancel}
                    aria-disabled={busy || undefined}
                    onclick={() => setOpen(false)}
                >
                    {secondaryButtonText}
                </Button>
                <Button
                    type="submit"
                    variant={danger ? "destructive" : "default"}
                    class={footerButton}
                    bind:ref={primary}
                    aria-disabled={busy || undefined}
                >
                    {#if status === "inactive"}
                        {primaryButtonText}
                    {:else}
                        <InlineLoading
                            class="text-inherit"
                            {status}
                            description={status === "active"
                                ? primaryButtonLoadingDescription
                                : successDescription}
                        />
                    {/if}
                </Button>
            </div>
        </form>
    </Dialog.Content>
</Dialog.Root>
