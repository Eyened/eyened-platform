<script module lang="ts">
    import type { Snippet } from "svelte";

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
        overview(): void;
        /** Status ▾ and the primary button, when the task shows them. */
        status?: Snippet;
        /** After "Mark ready" on the last set; shown at the top of the canvas. */
        notice?: { title: string; subtitle: string } | null;
    }
</script>

<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
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
            <Button variant="ghost" size="sm" onclick={() => task.overview()}
                >Task overview</Button
            >
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
            <!-- Below md, Status and the primary button wait for the narrow footer. -->
            {#if !narrow}{@render task.status?.()}{/if}
        </div>
    {/if}
    {#if narrow}
        {@render end?.()}
    {:else}
        <!-- In a task, the task config sets the strip. -->
        <LayoutPopover stripToggle={task === null} />
    {/if}
</header>
