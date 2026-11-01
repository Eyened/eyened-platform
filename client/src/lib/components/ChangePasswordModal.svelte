<script lang="ts">
    import { PASSWORD_HINT } from "$lib/admin/accountStatus";
    import { Modal } from "$lib/components/ui/modal/index.js";
    import { PasswordInput } from "$lib/components/ui/text-input/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getContext } from "svelte";

    let {
        open = $bindable(false),
        onCloseAutoFocus,
    }: { open?: boolean; onCloseAutoFocus?: (e: Event) => void } = $props();

    const { userManager } = getContext<GlobalContext>("globalContext");

    let current = $state("");
    let next = $state("");
    let confirm = $state("");
    let submitted = $state(false);

    const currentError = $derived(
        submitted && !current ? "Enter your current password" : undefined,
    );
    const nextError = $derived(
        submitted && !next ? "Enter a new password" : undefined,
    );
    const confirmError = $derived(
        submitted && next && confirm !== next
            ? "Passwords do not match"
            : undefined,
    );

    // Every open starts with empty fields.
    $effect(() => {
        if (open) {
            current = "";
            next = "";
            confirm = "";
            submitted = false;
        }
    });

    function onsubmit() {
        submitted = true;
        if (!current || !next || confirm !== next) return false;
        return userManager.changePassword(current, next);
    }
</script>

<Modal
    bind:open
    size="sm"
    modalHeading="Change password"
    primaryButtonText="Change password"
    primaryButtonLoadingDescription="Saving…"
    successDescription="Password changed"
    errorTitle="Password not changed"
    {onsubmit}
    {onCloseAutoFocus}
>
    <div class="flex flex-col gap-6">
        <PasswordInput
            labelText="Current password"
            autocomplete="current-password"
            bind:value={current}
            invalidText={currentError}
        />
        <PasswordInput
            labelText="New password"
            autocomplete="new-password"
            bind:value={next}
            helperText={PASSWORD_HINT}
            invalidText={nextError}
        />
        <PasswordInput
            labelText="Confirm new password"
            autocomplete="new-password"
            bind:value={confirm}
            invalidText={confirmError}
        />
    </div>
</Modal>
