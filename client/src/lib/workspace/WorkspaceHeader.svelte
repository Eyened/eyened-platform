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
        /** Who holds the set, with Claim / Give back, right after ◀ ▶. */
        holder?: Snippet;
        /** The set's move and its Set status menu, in the header or the narrow footer; unset when there is nothing to show. */
        status?: Snippet<["header" | "stacked"]>;
        /** After "Mark ready" on the last set; shown at the top of the canvas. */
        notice?: { title: string; subtitle: string } | null;
        /** While someone else holds the set; shown at the top of the canvas until closed. */
        holderNotice?: {
            title: string;
            subtitle: string;
            alert: boolean;
        } | null;
    }
</script>

<script lang="ts">
    import { Separator } from "$lib/components/ui/separator/index.js";
    import Launch from "carbon-icons-svelte/lib/Launch.svelte";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import ChevronLeft from "carbon-icons-svelte/lib/ChevronLeft.svelte";
    import ChevronRight from "carbon-icons-svelte/lib/ChevronRight.svelte";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import SaveStateSlot from "$lib/saving/SaveStateSlot.svelte";
    import { saveTracker } from "$lib/saving/saveTracker.svelte";
    import { MediaQuery } from "svelte/reactivity";
    import LayoutPopover from "./LayoutPopover.svelte";
    import PatientsOpen from "./PatientsOpen.svelte";

    // Below md the frame supplies the menu button (start) and the right-column button (end).
    let {
        task,
        narrow,
        patients = 1,
        start,
        end,
    }: {
        task: TaskHeader | null;
        narrow: boolean;
        /** Distinct patients in the catalogue, in view or not. */
        patients?: number;
        start?: Snippet;
        end?: Snippet;
    } = $props();

    // ASSUMPTION: words from xlg (82rem); below it the save state is an icon.
    const xlg = new MediaQuery("min-width: 82rem");
    // Below xlg a task header shrinks in place: no product name, short label, icon-only links.
    const compact = $derived(task !== null && !xlg.current);
    // Below lg (66rem) there is no room for the status tag either; ▾ still names the status.
    const lg = new MediaQuery("min-width: 66rem");
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
    {:else if !compact}
        <span class="px-4 text-heading-compact-01 text-text-primary"
            >EyeNED</span
        >
    {/if}
    <!-- ASSUMPTION: reserved slots in the overview's order. -->
    {#if task}
        {#if !narrow && (task.show.title || task.show.nav || task.show.overview || task.tag || task.holder)}
            {@render divider()}
        {/if}
        {#if task.show.title}
            {#if narrow || compact}
                <!-- Below xlg "Set" is dropped from view to fit; ◀ ▶ still say "set". -->
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
        {#if lg.current}{@render task.tag?.()}{/if}
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
        <!-- Below md the holder waits for the narrow footer. -->
        {#if !narrow}{@render task.holder?.()}{/if}
        {#if !narrow && task.show.overview}
            {#if compact}
                <IconButton
                    label="Task overview, opens in a new tab"
                    tooltip="Task overview"
                    href={task.overviewHref}
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    <Launch />
                </IconButton>
            {:else}
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
    {/if}
    <div class="min-w-0 flex-1"></div>
    <div class="contents" data-header-slot="patients-open">
        <PatientsOpen count={patients} />
    </div>
    <!-- Save state: 4 and 5; "Mark ready and next": 5. -->
    <div class="contents" data-header-slot="save-state">
        {#if narrow}
            <!-- The footer's save state isn't live, so this one announces it below md. -->
            <span role="status" class="sr-only">{saveTracker.text}</span>
        {:else}
            <SaveStateSlot iconOnly={!xlg.current} />
        {/if}
    </div>
    {#if task}
        <div class="contents" data-header-slot="mark-ready">
            <!-- Below md, the set's move and status wait for the narrow footer. -->
            {#if !narrow && task.status}
                {@render divider()}
                {@render task.status("header")}
            {/if}
        </div>
    {/if}
    {#if narrow}
        {@render end?.()}
    {:else}
        {@render divider()}
        <!-- In a task, the task config sets the strip. -->
        <LayoutPopover stripToggle={task === null} iconOnly={compact} />
    {/if}
</header>
