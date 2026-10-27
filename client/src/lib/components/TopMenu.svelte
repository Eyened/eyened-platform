<script lang="ts">
    import { resolve } from "$app/paths";
    import { page } from "$app/state";
    import { cn } from "$lib/utils.js";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import Menu from "carbon-icons-svelte/lib/Menu.svelte";
    import { getContext } from "svelte";
    import type { GlobalContext } from "../data/globalContext.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");

    // Carbon UI shell header. Below lg the links move into a side nav behind the menu button.
    function inSection(section: string): boolean {
        const path = page.url.pathname;
        return path === section || path.startsWith(`${section}/`);
    }

    let sideNavOpen = $state(false);
    let menuButton = $state<HTMLButtonElement | null>(null);

    function closeSideNav() {
        sideNavOpen = false;
        menuButton?.focus();
    }

    function onEscape(e: KeyboardEvent) {
        if (sideNavOpen && e.key === "Escape") closeSideNav();
    }

    // Close when Tab moves focus out of the nav, as Carbon's SideNav does.
    function onSideNavFocusOut(e: FocusEvent & { currentTarget: HTMLElement }) {
        const next = e.relatedTarget as Node | null;
        if (next && next !== menuButton && !e.currentTarget.contains(next)) {
            sideNavOpen = false;
        }
    }

    const navItem =
        "relative flex h-full items-center px-4 text-body-compact-01 text-text-secondary hover:bg-background-hover hover:text-text-primary active:bg-background-active aria-[current=page]:text-text-primary aria-[current=page]:after:absolute aria-[current=page]:after:inset-x-0 aria-[current=page]:after:bottom-0 aria-[current=page]:after:h-0.75 aria-[current=page]:after:bg-border-interactive";

    const sideNavItem =
        "relative flex min-h-8 items-center px-4 text-heading-compact-01 text-text-secondary hover:bg-background-hover hover:text-text-primary aria-[current=page]:bg-background-selected aria-[current=page]:text-text-primary aria-[current=page]:before:absolute aria-[current=page]:before:inset-y-0 aria-[current=page]:before:left-0 aria-[current=page]:before:w-0.75 aria-[current=page]:before:bg-border-interactive";
</script>

{#snippet links(itemClass: string, onclick?: () => void)}
    <li>
        <a
            href={resolve("/")}
            class={itemClass}
            aria-current={page.url.pathname === "/" ? "page" : undefined}
            {onclick}
        >
            Browser
        </a>
    </li>
    <li>
        <a
            href={resolve("/tasks")}
            class={itemClass}
            aria-current={inSection("/tasks") ? "page" : undefined}
            {onclick}
        >
            Tasks
        </a>
    </li>
    {#if globalContext.userManager.user?.is_admin}
        <li>
            <a
                href={resolve("/admin")}
                class={itemClass}
                aria-current={inSection("/admin") ? "page" : undefined}
                {onclick}
            >
                Admin
            </a>
        </li>
    {/if}
{/snippet}

<header
    class="fixed inset-x-0 top-0 z-50 flex h-12 items-center border-b border-border-subtle-00 bg-background"
>
    <button
        bind:this={menuButton}
        type="button"
        aria-label={sideNavOpen ? "Close menu" : "Open menu"}
        aria-expanded={sideNavOpen}
        aria-controls="side-nav"
        class={cn(
            "flex size-12 shrink-0 items-center justify-center border-x border-transparent text-icon-primary hover:bg-background-hover active:bg-background-active lg:hidden",
            sideNavOpen && "border-border-subtle-00 bg-layer-01",
        )}
        onclick={() => (sideNavOpen = !sideNavOpen)}
        onkeydown={onEscape}
    >
        {#if sideNavOpen}
            <Close size={20} aria-hidden="true" />
        {:else}
            <Menu size={20} aria-hidden="true" />
        {/if}
    </button>
    {#if sideNavOpen}
        <!-- Right after the menu button, so Tab moves from the button into the links. -->
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <nav
            id="side-nav"
            aria-label="Side navigation"
            class="fixed top-12 bottom-0 left-0 z-50 w-64 overflow-y-auto bg-background pt-4 lg:hidden"
            onkeydown={onEscape}
            onfocusout={onSideNavFocusOut}
        >
            <ul>
                {@render links(sideNavItem, () => (sideNavOpen = false))}
            </ul>
        </nav>
    {/if}
    <a
        href={resolve("/")}
        class="flex h-full items-center px-4 text-heading-compact-01 text-text-primary md:pe-8"
    >
        EyeNED
    </a>
    <nav
        aria-label="EyeNED"
        class="relative hidden h-full pl-4 before:absolute before:top-1/2 before:left-0 before:h-6 before:w-px before:-translate-y-1/2 before:bg-border-subtle-00 lg:block"
    >
        <ul class="flex h-full">
            {@render links(navItem)}
        </ul>
    </nav>
    <button
        type="button"
        aria-haspopup="dialog"
        class="ml-auto h-12 px-4 text-body-compact-01 text-text-primary hover:bg-background-hover active:bg-background-active"
        onclick={() => (globalContext.showUserMenu = true)}
    >
        {globalContext.userManager.user?.username}
    </button>
</header>

{#if sideNavOpen}
    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <div
        class="fixed inset-x-0 top-12 bottom-0 z-40 bg-overlay lg:hidden"
        onclick={closeSideNav}
    ></div>
{/if}
