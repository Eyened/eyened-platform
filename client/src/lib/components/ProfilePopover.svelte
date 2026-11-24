<script lang="ts">
    import ChangePasswordModal from "$lib/components/ChangePasswordModal.svelte";
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Popover from "$lib/components/ui/popover/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { theme, type ThemeChoice } from "$lib/theme.svelte";
    import Checkmark from "carbon-icons-svelte/lib/Checkmark.svelte";
    import { getContext } from "svelte";

    // Carbon Menu single-select: a checkmark in front of the chosen theme.
    const THEMES: { id: ThemeChoice; text: string }[] = [
        { id: "system", text: "System" },
        { id: "light", text: "Light" },
        { id: "dark", text: "Dark" },
    ];

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
        <div role="group" aria-labelledby="profile-theme-label" class="py-2">
            <p
                id="profile-theme-label"
                class="mb-1 px-4 text-label-01 text-text-secondary"
            >
                Theme
            </p>
            {#each THEMES as item (item.id)}
                {@const selected = theme.choice === item.id}
                <button
                    type="button"
                    aria-pressed={selected}
                    class="flex h-8 w-full cursor-pointer items-center gap-2 px-4 text-body-compact-01 text-text-primary hover:bg-layer-hover-01 aria-pressed:bg-layer-selected-01 aria-pressed:hover:bg-layer-selected-hover-01"
                    onclick={() => (theme.choice = item.id)}
                >
                    <Checkmark
                        size={16}
                        class={selected ? "fill-icon-primary" : "invisible"}
                    />
                    {item.text}
                </button>
            {/each}
        </div>
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
