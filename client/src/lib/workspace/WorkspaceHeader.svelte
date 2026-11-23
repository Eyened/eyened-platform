<script module lang="ts">
    import type { Snippet } from "svelte";
    import type { ResolvedPathname } from "$app/types";

    /** Task-mode set navigation and status. */
    export interface TaskHeader {
        label: string;
        /** The task's `task_panel` sections: the set label, ◀ ▶ and Task overview. */
        show: { title: boolean; nav: boolean; overview: boolean };
        prevDisabled: boolean;
        nextDisabled: boolean;
        /** The control showing a pending move, 1 s into its saves. */
        pending: "prev" | "next" | "primary" | null;
        prev(): void;
        next(): void;
        /** The Task overview page; the header opens it in a new tab. */
        overviewHref: ResolvedPathname;
        /** The set's status, right after the set label. */
        tag?: Snippet;
        /** The set's move and its Set status menu; unset when there is nothing to show. */
        status?: Snippet;
        /** After "Mark ready" on the last set; shown at the top of the canvas. */
        notice?: { title: string; subtitle: string } | null;
    }
</script>

<script lang="ts">
    import { Separator } from "$lib/components/ui/separator/index.js";
    import Launch from "carbon-icons-svelte/lib/Launch.svelte";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import ChevronLeft from "carbon-icons-svelte/lib/ChevronLeft.svelte";
    import ChevronRight from "carbon-icons-svelte/lib/ChevronRight.svelte";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { ContentSwitcher } from "$lib/components/ui/content-switcher/index.js";
    import { getContext } from "svelte";
    import SaveStateSlot from "$lib/saving/SaveStateSlot.svelte";
    import { MediaQuery } from "svelte/reactivity";
    import LayoutPopover from "./LayoutPopover.svelte";
    import type { ToolMode } from "./tools/registry";
    import type { Workspace } from "./workspace.svelte";
    import { writeToolMode } from "./workspacePrefs";

    // Below md the frame supplies the menu button (start) and the right-column button (end).
    let {
        task,
        narrow,
        start,
        end,
    }: {
        task: TaskHeader | null;
        narrow: boolean;
        start?: Snippet;
        end?: Snippet;
    } = $props();

    const workspace = getContext<Workspace>("workspace");
    // ASSUMPTION: words from xlg (82rem); below it the save state is an icon.
    const xlg = new MediaQuery("min-width: 82rem");
    const MODES = [
        { id: "browse", text: "Browse" },
        { id: "all", text: "All tools" },
    ];

    function setMode(id: string) {
        workspace.toolMode = id as ToolMode;
        writeToolMode(workspace.toolMode);
    }
</script>

{#snippet divider()}
    <!-- Divides the header's groups; decorative, so screen readers skip it. -->
    <Separator
        orientation="vertical"
        decorative
        class="mx-1 bg-border-subtle-01 data-[orientation=vertical]:h-6"
    />
{/snippet}

<header
    class="flex h-12 min-w-0 items-center gap-1 border-b border-border-subtle-01 bg-background pe-2"
    style="grid-area: header"
>
    {#if narrow}
        {@render start?.()}
    {:else}
        <span class="px-4 text-heading-compact-01 text-text-primary"
            >EyeNED</span
        >
    {/if}
    <!-- ASSUMPTION: reserved slots in the overview's order (plan decision 23). Patient context: 6; mode: 3. -->
    <div class="contents" data-header-slot="patient-context"></div>
    <div class="contents" data-header-slot="mode">
        {#if !task}
            <!-- A task is always All tools and shows no switcher. -->
            <ContentSwitcher
                size="sm"
                label="Mode"
                class="ms-2 w-fit"
                items={MODES}
                selectedId={workspace.toolMode}
                onchange={setMode}
            />
        {/if}
    </div>
    {#if task}
        {#if !narrow && (task.show.title || task.show.nav || task.show.overview || task.tag)}
            {@render divider()}
        {/if}
        {#if task.show.title}
            {#if narrow}
                <!-- Below md "Set" is dropped from view to fit 320 px; ◀ ▶ still say "set". -->
                <span class="sr-only">{task.label}</span>
                <span
                    aria-hidden="true"
                    class="ps-2 text-body-compact-01 whitespace-nowrap text-text-primary"
                    >{task.label.replace(/^Set /, "")}</span
                >
            {:else}
                <span
                    class="text-body-compact-01 whitespace-nowrap text-text-primary"
                    >{task.label}</span
                >
            {/if}
        {/if}
        <!-- Below md the set's status waits for the narrow footer. -->
        {#if !narrow}{@render task.tag?.()}{/if}
        {#if task.show.nav}
            <IconButton
                label="Previous set"
                data-set-control="prev"
                disabled={task.prevDisabled}
                aria-disabled={task.pending === "prev" || undefined}
                onclick={() => task.prev()}
            >
                {#if task.pending === "prev"}
                    <InlineLoading
                        class="min-h-0 w-auto"
                        status="active"
                        live={false}
                    />
                {:else}
                    <ChevronLeft />
                {/if}
            </IconButton>
            <IconButton
                label="Next set"
                data-set-control="next"
                disabled={task.nextDisabled}
                aria-disabled={task.pending === "next" || undefined}
                onclick={() => task.next()}
            >
                {#if task.pending === "next"}
                    <InlineLoading
                        class="min-h-0 w-auto"
                        status="active"
                        live={false}
                    />
                {:else}
                    <ChevronRight />
                {/if}
            </IconButton>
        {/if}
        {#if !narrow && task.show.overview}
            <!-- Carbon standalone Link with Launch: it opens another tab, so the set stays open. -->
            <!-- eslint-disable svelte/no-navigation-without-resolve -- overviewHref is a ResolvedPathname from resolve() -->
            <a
                href={task.overviewHref}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Task overview, opens in a new tab"
                class="inline-flex items-center gap-2 px-2 text-body-compact-01 whitespace-nowrap text-link-primary hover:text-link-primary-hover hover:underline"
            >
                Task overview
                <Launch aria-hidden="true" />
            </a>
            <!-- eslint-enable svelte/no-navigation-without-resolve -->
        {/if}
    {/if}
    <div class="min-w-0 flex-1"></div>
    <div class="contents" data-header-slot="patients-open"></div>
    <!-- Save state: 4 and 5; "Mark ready and next": 5. -->
    <div class="contents" data-header-slot="save-state">
        {#if !narrow}<SaveStateSlot iconOnly={!xlg.current} />{/if}
    </div>
    {#if task}
        <div class="contents" data-header-slot="mark-ready">
            <!-- Below md, the set's move and status wait for the narrow footer. -->
            {#if !narrow && task.status}
                {@render divider()}
                {@render task.status()}
            {/if}
        </div>
    {/if}
    {#if narrow}
        {@render end?.()}
    {:else}
        {@render divider()}
        <!-- In a task, the task config sets the strip. -->
        <LayoutPopover stripToggle={task === null} />
    {/if}
</header>
