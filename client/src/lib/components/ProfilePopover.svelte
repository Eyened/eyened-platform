<script lang="ts">
    import ChangePasswordModal from "$lib/components/ChangePasswordModal.svelte";
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getContext } from "svelte";

    // Carbon profile menu: the username opens a popover with the account actions.
    const globalContext = getContext<GlobalContext>("globalContext");
    const { userManager } = globalContext;

    let open = $state(false);
    let passwordOpen = $state(false);
    let trigger = $state<HTMLElement | null>(null);

    function changePassword() {
        open = false;
        passwordOpen = true;
    }

    function logout() {
        open = false;
        userManager.logout();
    }
</script>

<Popover.Root bind:open>
    <Popover.Trigger
        bind:ref={trigger}
        class="ml-auto h-12 min-w-0 truncate px-4 text-body-compact-01 text-text-primary hover:bg-background-hover active:bg-background-active"
    >
        {userManager.user?.username}
    </Popover.Trigger>
    <Popover.Content
        role="dialog"
        aria-label="Profile"
        align="end"
        sideOffset={0}
        class="w-64 rounded-popover px-0 py-2 drop-shadow-popover"
    >
        <p class="px-4 py-2 text-heading-compact-01">
            {userManager.user?.username}
        </p>
        <hr class="my-2 border-border-subtle-01" />
        {#if globalContext.passwordEnabled}
            <Button
                variant="ghost"
                class="w-full max-w-none"
                onclick={changePassword}
            >
                Change password
            </Button>
        {/if}
        <Button variant="ghost" class="w-full max-w-none" onclick={logout}>
            Log out
        </Button>
    </Popover.Content>
</Popover.Root>

<ChangePasswordModal
    bind:open={passwordOpen}
    onCloseAutoFocus={(e) => {
        e.preventDefault();
        trigger?.focus();
    }}
/>
