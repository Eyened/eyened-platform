<!--
@component
The viewer's region grid: header, left icon column and panel, tool options bar, canvas, pager and right column.
Below md there are no icon columns: a menu button opens the left column's content and a header button the right column's, both over the canvas.
The right column shows one panel at a time, Layers or Grading (Forms without a task); the route picks the first.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import * as Tabs from "$lib/components/ui/tabs/index.js";
    import LayersPanel from "$lib/layers/LayersPanel.svelte";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import Document from "carbon-icons-svelte/lib/Document.svelte";
    import Help from "carbon-icons-svelte/lib/Help.svelte";
    import Image from "carbon-icons-svelte/lib/Image.svelte";
    import Information from "carbon-icons-svelte/lib/Information.svelte";
    import Launch from "carbon-icons-svelte/lib/Launch.svelte";
    import Layers from "carbon-icons-svelte/lib/Layers.svelte";
    import Menu from "carbon-icons-svelte/lib/Menu.svelte";
    import RightPanelOpen from "carbon-icons-svelte/lib/RightPanelOpen.svelte";
    import { getContext, onMount, tick, untrack, type Snippet } from "svelte";
    import SaveStateSlot from "$lib/saving/SaveStateSlot.svelte";
    import { MediaQuery } from "svelte/reactivity";
    import {
        saveTracker,
        type RevealTarget,
    } from "$lib/saving/saveTracker.svelte";
    import { titleText, type ViewportTitle } from "./imageMeta";
    import type { ImageGET } from "../../types/openapi_types";
    import HelpPanel from "./HelpPanel.svelte";
    import InfoPanel from "./InfoPanel.svelte";
    import ImagesPanel from "./ImagesPanel.svelte";
    import LayoutPopover from "./LayoutPopover.svelte";
    import MagnifierPanel from "./MagnifierPanel.svelte";
    import Pager from "./Pager.svelte";
    import { GAP_PX } from "./tools/paletteLayout";
    import ToolOptionsBar from "./tools/ToolOptionsBar.svelte";
    import ToolPalette from "./tools/ToolPalette.svelte";
    import ThumbnailStrip from "./ThumbnailStrip.svelte";
    import ViewportGrid from "./ViewportGrid.svelte";
    import type { Workspace } from "./workspace.svelte";
    import WorkspaceHeader, { type TaskHeader } from "./WorkspaceHeader.svelte";
    import {
        readLeftPanel,
        readRightOpen,
        writeLeftPanel,
        writeRightOpen,
        type LeftPanel,
    } from "./workspacePrefs";

    let {
        viewer,
        tile,
        titleFor,
        instanceFor,
        onaddimages,
        task = null,
        emptyMessage = null,
        forms,
        startOnGrading = false,
    }: {
        viewer: Snippet<[string]>;
        tile: Snippet<[string]>;
        titleFor: (imageId: string) => ViewportTitle | null;
        /** The image's metadata; for an OCT's `_proj`, its OCT's. */
        instanceFor: (imageId: string) => ImageGET | null;
        onaddimages: () => void;
        task?: TaskHeader | null;
        emptyMessage?: string | null;
        /** The Grading or Forms panel's content. */
        forms?: Snippet;
        /** Below md, open on Grading with focus on the footer's button (the last set left from there). */
        startOnGrading?: boolean;
    } = $props();

    const workspace = getContext<Workspace>("workspace");
    const uid = $props.id();
    const md = new MediaQuery("min-width: 42rem");
    const xlg = new MediaQuery("min-width: 82rem");
    const narrow = $derived(!md.current);
    const RIGHT_OPEN_PX = 288;
    const RAIL_PX = 48;

    // Images starts closed while the strip is on: the strip already shows the catalogue.
    // ASSUMPTION: read once at mount (plan decision 22).
    const defaultLeft: LeftPanel | null = workspace.strip ? null : "images";
    /** The wide left panel: the stored choice, else the default. */
    function initialLeft(): LeftPanel | null {
        const stored = readLeftPanel();
        return stored === undefined ? defaultLeft : stored;
    }

    // Wide state: stored per user.
    let left: LeftPanel | null = $state(md.current ? initialLeft() : null);
    let rightChoice: boolean | undefined = $state(readRightOpen());
    // The user's choice beats the below-xlg default.
    const rightOpen = $derived(rightChoice ?? xlg.current);
    type RightPanel = "layers" | "forms";
    // The grade route opens on Grading, /view on Layers; never stored.
    let panel: RightPanel = $state(untrack(() => (task ? "forms" : "layers")));

    // Narrow state: one overlay at a time, never stored.
    let overlay: "menu" | "right" | null = $state(null);
    let menuTab: LeftPanel = $state("images");
    let layoutOpen = $state(false);

    const leftShown = $derived(
        narrow ? (overlay === "menu" ? menuTab : null) : left,
    );
    const rightShown = $derived(narrow ? overlay === "right" : rightOpen);
    const overlayOpen = $derived(narrow && overlay !== null);
    const formsName = $derived(task ? "Grading" : "Forms");
    const footer = $derived(
        narrow && task !== null && !!(task.tag || task.holder || task.status),
    );
    // Closing the holder notice lasts for this set; the next set is a page load.
    let holderNoticeClosed = $state(false);
    let footerHeight = $state(0);
    // The header's words on the narrow panels button while something couldn't save.
    const saveFailure = $derived(
        saveTracker.worst === "error" ? saveTracker.text : "",
    );

    onMount(() => {
        if (startOnGrading && narrow) void reopenGrading();
    });

    async function reopenGrading() {
        panel = "forms";
        overlay = "right";
        opener = byControls(`${uid}-right-panels`);
        await tick();
        (
            document.querySelector<HTMLElement>(
                '[data-set-footer] [data-set-control="primary"]',
            ) ?? document.getElementById(`${uid}-forms-title`)
        )?.focus();
    }
    const layersSubtitle = $derived.by(() => {
        const position = workspace.selected;
        const imageId = workspace.slots[position]?.imageId ?? null;
        const title = imageId ? titleFor(imageId) : null;
        const what = title
            ? titleText({ ...title, demographics: "" })
            : imageId || !workspace.loaded
              ? "Loading…"
              : "Empty";
        return `Viewport ${position + 1} · ${what}`;
    });
    let opener: HTMLElement | null = null;
    // The palette gets what the rail leaves after the bottom group and one gap.
    let railHeight = $state(0);
    let bottomHeight = $state(0);
    const paletteSpace = $derived(railHeight - bottomHeight - GAP_PX);
    // The Magnifier is placed and clamped inside the canvas.
    let canvasWidth = $state(0);
    let canvasHeight = $state(0);

    const LEFT_PANELS = [
        { id: "images", label: "Images", Icon: Image },
        { id: "info", label: "Info", Icon: Information },
        { id: "help", label: "Help", Icon: Help },
    ] as const;
    const RIGHT_PANELS = [
        { id: "layers", Icon: Layers },
        { id: "forms", Icon: Document },
    ] as const;
    const panelName = (id: RightPanel) =>
        id === "layers" ? "Layers" : formsName;
    /** IconButton's tooltip trigger replaces any id, so buttons are found by what they control. */
    const byControls = (id: string) =>
        document.querySelector<HTMLElement>(`[aria-controls="${id}"]`);

    function setRight(open: boolean) {
        rightChoice = open;
        writeRightOpen(open);
    }

    /** Stay and the header's "couldn't save" bring the grader to the item: selected in a viewport showing its image, on its pane's Retry. */
    async function revealItem(target: Extract<RevealTarget, { to: "layers" }>) {
        const position = workspace.slots.findIndex(
            (slot) => slot.imageId === target.imageId,
        );
        // ASSUMPTION: when no viewport shows the image, Layers opens without a selection change.
        if (position !== -1) workspace.select(position);
        const layers =
            position !== -1 ? workspace.selectedViewport?.layers : undefined;
        if (layers) {
            const { item } = target;
            layers.selection.select(
                item.kind === "segmentation"
                    ? {
                          kind: "segmentation",
                          item: layers.mainViewerContext.segmentationContext.getSegmentationItem(
                              item.segmentation,
                          ),
                      }
                    : item,
            );
        }
        workspace.setLayerSection(target.section, true);
        workspace.layersTab = "layers";
        panel = "layers";
        if (narrow) overlay = "right";
        else setRight(true);
        await tick();
        // The pane's Retry; while the save still runs there is none, so the selected row's name.
        // With no viewport on the image nothing is selected, so the Layers panel's heading.
        (
            document.querySelector<HTMLElement>("[data-save-retry]") ??
            document.querySelector<HTMLElement>(
                "[data-layers-list] [data-layer-row].selected button",
            ) ??
            document.getElementById(`${uid}-layers-title`)
        )?.focus();
    }
    /** Comments, and the status in the narrow footer, live in Grading: show it first. */
    async function reveal(target: Exclude<RevealTarget, { to: "focus" }>) {
        if (target.to === "layers") return revealItem(target);
        if (!target.footer || narrow) {
            panel = "forms";
            if (narrow) overlay = "right";
            else setRight(true);
            await tick();
        }
        target.focus();
    }
    $effect(() => {
        saveTracker.revealer = reveal;
        return () => {
            if (saveTracker.revealer === reveal) saveTracker.revealer = null;
        };
    });

    /** Opening a left panel moves focus to its heading (overview §3). */
    async function focusPanel(panel: LeftPanel) {
        await tick();
        document.getElementById(`${uid}-${panel}-title`)?.focus();
    }

    function toggleLeft(panel: LeftPanel, e: MouseEvent) {
        opener = e.currentTarget as HTMLElement;
        left = left === panel ? null : panel;
        writeLeftPanel(left);
        if (left) void focusPanel(left);
    }

    /** Another panel's icon swaps it in; the shown panel's icon folds the column. Below md only the swap applies. */
    function toggleRight(id: RightPanel, e: MouseEvent) {
        // Below md the opener stays the header button, so Esc returns focus there and not into the closed overlay.
        if (!narrow) opener = e.currentTarget as HTMLElement;
        if (!narrow && rightOpen && panel === id) {
            setRight(false);
            return;
        }
        panel = id;
        if (!narrow) setRight(true);
    }

    /** Below md: the menu or the right column, opened from its header button. */
    async function toggleOverlay(next: "menu" | "right", e: MouseEvent) {
        opener = e.currentTarget as HTMLElement;
        layoutOpen = false;
        overlay = overlay === next ? null : next;
        if (overlay === null) return;
        await tick();
        if (next === "right")
            document.getElementById(`${uid}-${panel}-title`)?.focus();
        else
            document
                .getElementById(`${uid}-left`)
                ?.querySelector<HTMLElement>("a, button")
                ?.focus();
    }

    /** Esc or a press on the scrim: close, and return focus to the opener. */
    async function dismiss() {
        overlay = null;
        // The opener may sit in the canvas, which stays inert until the DOM updates.
        await tick();
        opener?.focus();
    }

    function onkeydown(e: KeyboardEvent) {
        if (e.key !== "Escape" || !overlayOpen) return;
        e.preventDefault();
        void dismiss();
    }

    // F1 opens Help from anywhere but a text field, a dialog or an open ⋯ list.
    function onwindowkeydown(e: KeyboardEvent) {
        if (e.key !== "F1") return;
        const target = e.target as Element | null;
        if (
            target?.closest(
                'input, textarea, select, [contenteditable="true"], [role="dialog"], [data-slot="overflow-menu"]',
            )
        )
            return;
        e.preventDefault();
        void openHelp();
    }

    async function openHelp() {
        // A repeat F1 while the menu is open would otherwise record an element inside it.
        if (!overlayOpen) opener = document.activeElement as HTMLElement | null;
        if (narrow) {
            layoutOpen = false;
            overlay = "menu";
            menuTab = "help";
            await tick();
            document.getElementById(`${uid}-help-title`)?.focus();
            return;
        }
        left = "help";
        writeLeftPanel(left);
        void focusPanel("help");
    }

    function openLayout() {
        overlay = null;
        layoutOpen = true;
    }

    async function chooseImage() {
        opener = document.activeElement as HTMLElement | null;
        if (narrow) {
            overlay = "menu";
            menuTab = "images";
        } else {
            left = "images";
            writeLeftPanel(left);
        }
        await tick();
        document
            .getElementById(`${uid}-images`)
            ?.querySelector<HTMLElement>('[role="option"][tabindex="0"]')
            ?.focus();
    }

    async function imageLoaded() {
        if (!narrow) return;
        overlay = null;
        await tick();
        // Loading unmounts the Choose button; fall back to the selected viewport's controls.
        (opener?.isConnected
            ? opener
            : document.querySelector<HTMLElement>(
                  '[aria-current="true"] [tabindex="0"]',
              )
        )?.focus();
    }

    // Crossing md closes an open overlay; the wide side reads the stored prefs again,
    // and focus that was in a panel moves to the button that controls it at the new width.
    let wasNarrow = untrack(() => narrow);
    $effect.pre(() => {
        const now = narrow;
        if (now === wasNarrow) return;
        wasNarrow = now;
        untrack(() => void crossed(now));
    });

    async function crossed(nowNarrow: boolean) {
        const active = document.activeElement;
        const within = (id: string) =>
            !!active && !!document.getElementById(id)?.contains(active);
        const inLeft = within(`${uid}-left`);
        const inRight = within(`${uid}-right-panels`);
        const tab = menuTab;
        overlay = null;
        layoutOpen = false;
        if (!nowNarrow) {
            left = initialLeft();
            rightChoice = readRightOpen();
        }
        await tick();
        if (inLeft)
            byControls(nowNarrow ? `${uid}-left` : `${uid}-${tab}`)?.focus();
        else if (inRight)
            byControls(
                nowNarrow ? `${uid}-right-panels` : `${uid}-${panel}`,
            )?.focus();
    }
</script>

{#snippet tools(orientation: "vertical" | "horizontal")}
    <ToolPalette available={paletteSpace} {orientation} />
{/snippet}

{#snippet headerStart()}
    <IconButton
        label={overlay === "menu" ? "Hide menu" : "Show menu"}
        aria-controls="{uid}-left"
        onclick={(e) => toggleOverlay("menu", e)}
    >
        {#if overlay === "menu"}<Close />{:else}<Menu />{/if}
    </IconButton>
    <LayoutPopover
        anchor={`[aria-controls="${uid}-left"]`}
        bind:open={layoutOpen}
        stripToggle={task === null}
    />
{/snippet}

{#snippet headerEnd()}
    <IconButton
        label="{overlay === 'right'
            ? 'Hide'
            : 'Show'} Layers and {formsName}{saveFailure
            ? `, ${saveFailure}`
            : ''}"
        aria-controls="{uid}-right-panels"
        class={saveFailure
            ? "relative after:absolute after:end-2 after:top-2 after:size-2 after:rounded-full after:bg-support-error"
            : undefined}
        onclick={(e) => toggleOverlay("right", e)}
    >
        {#if overlay === "right"}<Close />{:else}<RightPanelOpen />{/if}
    </IconButton>
{/snippet}

{#snippet panelSwitch()}
    {#each RIGHT_PANELS as item (item.id)}
        <!-- Selected: layer-selected plus a 3 px border-interactive bar on the panel side, like the side nav's current item. -->
        <IconButton
            label={panelName(item.id)}
            aria-pressed={rightShown && panel === item.id}
            aria-controls="{uid}-{item.id}"
            class="relative aria-pressed:bg-layer-selected-01 aria-pressed:before:absolute aria-pressed:before:inset-y-0 aria-pressed:before:start-0 aria-pressed:before:w-0.75 aria-pressed:before:bg-border-interactive"
            onclick={(e) => toggleRight(item.id, e)}
        >
            <item.Icon />
        </IconButton>
    {/each}
{/snippet}

<svelte:window onkeydown={onwindowkeydown} />

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
    class="frame"
    class:narrow
    style="--rail: {narrow ? '0px' : `${RAIL_PX}px`}; --left: {left && !narrow
        ? '256px'
        : '0px'}; --right: {narrow
        ? '0px'
        : rightOpen
          ? `${RIGHT_OPEN_PX}px`
          : `${RAIL_PX}px`};"
    {onkeydown}
>
    <WorkspaceHeader {task} {narrow} start={headerStart} end={headerEnd} />
    {#if !narrow}
        <nav
            class="rail"
            aria-label="Tools and panels"
            bind:clientHeight={railHeight}
        >
            {@render tools("vertical")}
            <div class="rail-bottom" bind:offsetHeight={bottomHeight}>
                {#each LEFT_PANELS as panel (panel.id)}
                    <IconButton
                        label={panel.label}
                        aria-pressed={left === panel.id}
                        aria-controls="{uid}-{panel.id}"
                        onclick={(e) => toggleLeft(panel.id, e)}
                    >
                        <panel.Icon />
                    </IconButton>
                {/each}
            </div>
        </nav>
    {/if}
    <div
        id="{uid}-left"
        class="left"
        hidden={narrow ? overlay !== "menu" : left === null}
    >
        {#if narrow}
            <!-- ASSUMPTION: Carbon puts header links above the left panel items; ghost buttons as in the wide header. -->
            <nav
                aria-label="Menu"
                class="flex flex-col border-b border-border-subtle-01 py-2"
            >
                {#if task}
                    <!-- Opens another tab, so the set stays open; the menu closes. -->
                    <Button
                        variant="ghost"
                        size="sm"
                        class="justify-start"
                        href={task.overviewHref}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label="Task overview, opens in a new tab"
                        onclick={() => (overlay = null)}
                    >
                        Task overview
                        <Launch aria-hidden="true" />
                    </Button>
                {/if}
                <Button
                    variant="ghost"
                    size="sm"
                    class="justify-start"
                    onclick={openLayout}>Layout…</Button
                >
            </nav>
            {@render tools("horizontal")}
            <!-- ASSUMPTION: tabs switch the sections below without Tabs.Content, so both widths share one markup. -->
            <Tabs.Root
                bind:value={() => menuTab, (v) => (menuTab = v as LeftPanel)}
                class="px-4 pt-2"
            >
                <Tabs.List aria-label="Panels">
                    {#each LEFT_PANELS as panel (panel.id)}
                        <Tabs.Trigger value={panel.id}
                            >{panel.label}</Tabs.Trigger
                        >
                    {/each}
                </Tabs.List>
            </Tabs.Root>
        {/if}
        {#each LEFT_PANELS as panel (panel.id)}
            <section
                id="{uid}-{panel.id}"
                aria-labelledby="{uid}-{panel.id}-title"
                hidden={leftShown !== panel.id}
            >
                <h2
                    id="{uid}-{panel.id}-title"
                    tabindex="-1"
                    class="px-4 pt-3 pb-2 text-heading-compact-01 text-text-primary"
                >
                    {panel.label}
                </h2>
                {#if panel.id === "images"}
                    <ImagesPanel
                        {titleFor}
                        {instanceFor}
                        {onaddimages}
                        onloaded={imageLoaded}
                    />
                {:else if panel.id === "info"}
                    <InfoPanel
                        {instanceFor}
                        subtitle={layersSubtitle}
                        shown={leftShown === "info"}
                    />
                {:else if panel.id === "help"}
                    <HelpPanel shown={leftShown === "help"} />
                {/if}
            </section>
        {/each}
    </div>
    <div class="tool-options" inert={overlayOpen}><ToolOptionsBar /></div>
    <main
        class="canvas"
        inert={overlayOpen}
        bind:clientWidth={canvasWidth}
        bind:clientHeight={canvasHeight}
    >
        {#if emptyMessage}
            <p class="m-8 text-body-compact-01 text-text-primary">
                {emptyMessage}
            </p>
        {:else}
            <!-- Over the bottom of the canvas, above the bottom viewports' view bars, so the images don't move. -->
            <div class="notices">
                <!-- Always mounted, so screen readers announce the notice when it appears. -->
                <div role="status">
                    {#if task?.notice}
                        <InlineNotification
                            kind="success"
                            class="shadow-popover"
                            highContrast
                            title={task.notice.title}
                            subtitle={task.notice.subtitle}
                            role="none"
                        />
                    {/if}
                </div>
                <!-- Outside the live region: on arrival it is just there; after a lost Claim it is an alert. -->
                {#if task?.holderNotice && !holderNoticeClosed}
                    <InlineNotification
                        kind="warning"
                        class="shadow-popover"
                        highContrast
                        title={task.holderNotice.title}
                        subtitle={task.holderNotice.subtitle}
                        role={task.holderNotice.alert ? "alert" : "none"}
                        onclose={() => (holderNoticeClosed = true)}
                    />
                {/if}
            </div>
            {#if workspace.strip}
                <ThumbnailStrip {tile} {titleFor} />
            {/if}
            <ViewportGrid {viewer} {titleFor} onchooseimage={chooseImage} />
            <MagnifierPanel
                width={canvasWidth}
                height={canvasHeight}
                {titleFor}
            />
        {/if}
    </main>
    <div class="pager" inert={overlayOpen}><Pager /></div>
    <aside class="right" aria-label="Layers and {formsName.toLowerCase()}">
        {#if !narrow}
            <div class="right-rail">{@render panelSwitch()}</div>
        {/if}
        <div
            id="{uid}-right-panels"
            class="right-panels"
            hidden={!rightShown}
            style:scroll-padding-bottom={footer
                ? `${footerHeight}px`
                : undefined}
        >
            {#if narrow}
                <div
                    role="group"
                    aria-label="Panels"
                    class="flex border-b border-border-subtle-01 px-2"
                >
                    {@render panelSwitch()}
                </div>
            {/if}
            <section
                id="{uid}-layers"
                aria-labelledby="{uid}-layers-title"
                hidden={panel !== "layers"}
            >
                <h2
                    id="{uid}-layers-title"
                    tabindex="-1"
                    class="px-4 pt-3 pb-2 text-heading-compact-01 text-text-primary"
                >
                    Layers
                </h2>
                <LayersPanel
                    subtitle={layersSubtitle}
                    shown={rightShown && panel === "layers"}
                />
            </section>
            <section
                id="{uid}-forms"
                aria-labelledby="{uid}-forms-title"
                hidden={panel !== "forms"}
            >
                <h2
                    id="{uid}-forms-title"
                    tabindex="-1"
                    class="px-4 pt-3 pb-2 text-heading-compact-01 text-text-primary"
                >
                    {formsName}
                </h2>
                {@render forms?.()}
                {#if footer && task}
                    <!-- Pinned to the bottom of the overlay; the scroll area keeps focused rows above it. -->
                    <div
                        class="footer"
                        data-set-footer
                        bind:offsetHeight={footerHeight}
                    >
                        <!-- At 320 px a tag and "1 form couldn't save" don't fit on one line, so it wraps. -->
                        <div class="flex min-h-6 flex-wrap items-center gap-2">
                            {@render task.tag?.()}{@render task.holder?.()}
                            <div class="ms-auto">
                                <SaveStateSlot
                                    iconOnly={false}
                                    live={false}
                                    reserve={false}
                                />
                            </div>
                        </div>
                        {@render task.status?.("stacked")}
                    </div>
                {/if}
            </section>
        </div>
    </aside>
    {#if overlayOpen}
        <div class="scrim" aria-hidden="true" onclick={dismiss}></div>
    {/if}
</div>

<style>
    .frame {
        position: relative;
        display: grid;
        flex: 1;
        min-height: 0;
        /* Keeps the viewer's z-indexes below menus portalled to <body>. */
        isolation: isolate;
        grid-template-columns: var(--rail) var(--left) minmax(0, 1fr) var(
                --right
            );
        grid-template-rows: 48px minmax(32px, auto) minmax(0, 1fr) auto;
        /* The options bar spans the rail and the left panel, so the armed tool's icon sits under the tool column. */
        grid-template-areas:
            "header header header header"
            "tools tools tools right"
            "rail left canvas right"
            "rail left pager right";
    }
    .rail {
        grid-area: rail;
        display: flex;
        flex-direction: column;
        overflow-y: auto;
        /* The 48 px split slot is 1 px wider than the content box beside the border. */
        overflow-x: hidden;
        background: var(--color-layer-01);
        border-inline-end: 1px solid var(--color-border-subtle-01);
    }
    /* At short heights the bottom group joins the top one and they scroll together (S2 side navigation). */
    .rail-bottom {
        display: flex;
        flex-direction: column;
        margin-top: auto;
    }
    .left {
        grid-area: left;
        overflow-y: auto;
        background: var(--color-layer-01);
    }
    .tool-options {
        grid-area: tools;
        background: var(--color-layer-01);
        border-bottom: 1px solid var(--color-border-subtle-01);
    }
    .canvas {
        grid-area: canvas;
        position: relative;
        display: flex;
        flex-direction: column;
        min-width: 0;
        min-height: 0;
    }
    .notices {
        position: absolute;
        inset-inline: 16px;
        bottom: 40px;
        z-index: 10;
        display: flex;
        flex-direction: column;
        gap: 8px;
        pointer-events: none;
    }
    .notices > :global(*) {
        pointer-events: auto;
    }
    .pager {
        grid-area: pager;
    }
    .right {
        grid-area: right;
        display: flex;
        flex-direction: row-reverse;
        min-height: 0;
        background: var(--color-layer-01);
        border-inline-start: 1px solid var(--color-border-subtle-01);
    }
    .right-rail {
        display: flex;
        flex: none;
        flex-direction: column;
        width: 48px;
    }
    .right-panels {
        flex: 1;
        min-width: 0;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
    }
    /* The shown panel fills the column; Layers shares its height between list and pane, and below 21rem the column scrolls (WCAG 1.4.10). */
    .right-panels > section:not([hidden]) {
        display: flex;
        flex: 1;
        flex-direction: column;
        min-height: 0;
    }
    .right-panels > section[id$="-layers"]:not([hidden]) {
        min-height: 21rem;
    }
    .footer {
        position: sticky;
        bottom: 0;
        margin-top: auto;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        padding: 0.5rem 1rem 0.75rem;
        background: var(--color-layer-01);
        border-top: 1px solid var(--color-border-subtle-01);
    }
    .narrow .right {
        border-inline-start: 0;
    }
    /* Carbon left panel: 256 px over the canvas, flush left. */
    .narrow .left:not([hidden]) {
        /* A grid area would be the containing block, and the left one is 0 px wide. */
        grid-area: auto;
        position: absolute;
        top: 48px;
        bottom: 0;
        left: 0;
        z-index: 20;
        width: min(256px, calc(100% - 48px));
    }
    /* Carbon right panel: floats over the canvas, flush right. */
    .narrow .right-panels:not([hidden]) {
        position: absolute;
        top: 48px;
        bottom: 0;
        right: 0;
        z-index: 20;
        width: min(288px, calc(100% - 48px));
        background: var(--color-layer-01);
    }
    .scrim {
        position: absolute;
        inset: 48px 0 0 0;
        z-index: 10;
        background: var(--color-overlay);
    }
</style>
