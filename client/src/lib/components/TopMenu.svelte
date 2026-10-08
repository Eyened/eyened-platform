<script lang="ts">
    import { resolve } from "$app/paths";
    import { page } from "$app/state";
    import { getContext } from "svelte";
    import type { GlobalContext } from "../data/globalContext.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");

    // Carbon UI shell header.
    function inSection(section: string): boolean {
        const path = page.url.pathname;
        return path === section || path.startsWith(`${section}/`);
    }

    const navItem =
        "relative flex h-full items-center px-4 text-body-compact-01 text-text-secondary hover:bg-background-hover hover:text-text-primary active:bg-background-active aria-[current=page]:text-text-primary aria-[current=page]:after:absolute aria-[current=page]:after:inset-x-0 aria-[current=page]:after:bottom-0 aria-[current=page]:after:h-0.75 aria-[current=page]:after:bg-border-interactive";
</script>

<header
    class="fixed inset-x-0 top-0 z-50 flex h-12 items-center border-b border-border-subtle-00 bg-background"
>
    <a
        href={resolve("/")}
        class="flex h-full items-center pr-8 pl-4 text-heading-compact-01 text-text-primary"
    >
        EyeNED
    </a>
    <nav
        aria-label="EyeNED"
        class="relative h-full pl-4 before:absolute before:top-1/2 before:left-0 before:h-6 before:w-px before:-translate-y-1/2 before:bg-border-subtle-00"
    >
        <ul class="flex h-full">
            <li>
                <a
                    href={resolve("/")}
                    class={navItem}
                    aria-current={page.url.pathname === "/"
                        ? "page"
                        : undefined}
                >
                    Browser
                </a>
            </li>
            <li>
                <a
                    href={resolve("/tasks")}
                    class={navItem}
                    aria-current={inSection("/tasks") ? "page" : undefined}
                >
                    Tasks
                </a>
            </li>
            {#if globalContext.userManager.user.is_admin}
                <li>
                    <a
                        href={resolve("/admin")}
                        class={navItem}
                        aria-current={inSection("/admin") ? "page" : undefined}
                    >
                        Admin
                    </a>
                </li>
            {/if}
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
