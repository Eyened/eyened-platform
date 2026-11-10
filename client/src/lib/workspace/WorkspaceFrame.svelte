<!--
@component
The viewer's region grid: header, left icon column and panel, tool options bar, canvas, pager and right column.
Below md there are no icon columns: a menu button opens the left column's content and a header button the right column's, both over the canvas.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import * as Tabs from "$lib/components/ui/tabs/index.js";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import Document from "carbon-icons-svelte/lib/Document.svelte";
    import Help from "carbon-icons-svelte/lib/Help.svelte";
    import Image from "carbon-icons-svelte/lib/Image.svelte";
    import Information from "carbon-icons-svelte/lib/Information.svelte";
    import Layers from "carbon-icons-svelte/lib/Layers.svelte";
    import Menu from "carbon-icons-svelte/lib/Menu.svelte";
    import RightPanelOpen from "carbon-icons-svelte/lib/RightPanelOpen.svelte";
    import { getContext, tick, untrack, type Snippet } from "svelte";
    import { MediaQuery } from "svelte/reactivity";
    import type { ViewportTitle } from "./imageMeta";
    import ImagesListShell from "./ImagesListShell.svelte";
    import LayoutPopover from "./LayoutPopover.svelte";
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
        onaddimages,
        task = null,
        emptyMessage = null,
    }: {
        viewer: Snippet<[string]>;
        tile: Snippet<[string]>;
        titleFor: (imageId: string) => ViewportTitle | null;
        onaddimages: () => void;
        task?: TaskHeader | null;
        emptyMessage?: string | null;
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
    let expanded = $state({ layers: true, forms: true });

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
    let opener: HTMLElement | null = null;
    // The palette gets what the rail leaves after the bottom group and one gap.
    let railHeight = $state(0);
    let bottomHeight = $state(0);
    const paletteSpace = $derived(railHeight - bottomHeight - GAP_PX);

    const LEFT_PANELS = [
        { id: "images", label: "Images", Icon: Image },
        { id: "info", label: "Info", Icon: Information },
        { id: "help", label: "Help", Icon: Help },
    ] as const;
    /** IconButton's tooltip trigger replaces any id, so buttons are found by what they control. */
    const byControls = (id: string) =>
        document.querySelector<HTMLElement>(`[aria-controls="${id}"]`);

    function setRight(open: boolean) {
        rightChoice = open;
        writeRightOpen(open);
    }

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

    const shown = (section: "layers" | "forms") =>
        rightOpen && expanded[section];

    function toggleSection(section: "layers" | "forms", e: MouseEvent) {
        opener = e.currentTarget as HTMLElement;
        if (shown(section)) {
            expanded = { ...expanded, [section]: false };
            if (!expanded.layers && !expanded.forms) {
                setRight(false);
                expanded = { layers: true, forms: true };
            }
            return;
        }
        if (!rightOpen) expanded = { layers: false, forms: false };
        expanded = { ...expanded, [section]: true };
        setRight(true);
    }

    /** Below md: the menu or the right column, opened from its header button. */
    async function toggleOverlay(next: "menu" | "right", e: MouseEvent) {
        opener = e.currentTarget as HTMLElement;
        layoutOpen = false;
        overlay = overlay === next ? null : next;
        if (overlay === null) return;
        await tick();
        if (next === "right")
            document.getElementById(`${uid}-layers-title`)?.focus();
        else
            document
                .getElementById(`${uid}-left`)
                ?.querySelector<HTMLElement>("button")
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
        opener = document.activeElement as HTMLElement | null;
        if (narrow) {
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

    function openOverview() {
        overlay = null;
        task?.overview();
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
            ?.querySelector<HTMLElement>("li button")
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
                nowNarrow ? `${uid}-right-panels` : `${uid}-layers`,
            )?.focus();
    }

    // ASSUMPTION: the root <Toaster> reads these (plan decision 16): bottom right of the canvas, above the pager
    // and the bottom-right viewport's 32 px view bar, with an 8 px gap.
    $effect(() => {
        const style = document.body.style;
        style.setProperty(
            "--viewer-toast-right",
            `${narrow ? 16 : (rightOpen ? RIGHT_OPEN_PX : RAIL_PX) + 16}px`,
        );
        style.setProperty(
            "--viewer-toast-bottom",
            `${workspace.showPager ? 72 : 40}px`,
        );
        return () => {
            style.removeProperty("--viewer-toast-right");
            style.removeProperty("--viewer-toast-bottom");
        };
    });
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
        label="{overlay === 'right' ? 'Hide' : 'Show'} Layers and {formsName}"
        aria-controls="{uid}-right-panels"
        onclick={(e) => toggleOverlay("right", e)}
    >
        {#if overlay === "right"}<Close />{:else}<RightPanelOpen />{/if}
    </IconButton>
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
                    <Button
                        variant="ghost"
                        size="sm"
                        class="justify-start"
                        onclick={openOverview}>Task overview</Button
                    >
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
                    <ImagesListShell
                        {titleFor}
                        {onaddimages}
                        onloaded={imageLoaded}
                    />
                {/if}
            </section>
        {/each}
    </div>
    <div class="tool-options" inert={overlayOpen}><ToolOptionsBar /></div>
    <main class="canvas" inert={overlayOpen}>
        {#if emptyMessage}
            <p class="m-8 text-body-compact-01 text-text-primary">
                {emptyMessage}
            </p>
        {:else}
            {#if workspace.strip}
                <ThumbnailStrip {tile} {titleFor} />
            {/if}
            <ViewportGrid {viewer} {titleFor} onchooseimage={chooseImage} />
        {/if}
    </main>
    <div class="pager" inert={overlayOpen}><Pager /></div>
    <aside class="right" aria-label="Layers and {formsName.toLowerCase()}">
        {#if !narrow}
            <div class="right-rail">
                <IconButton
                    label="{shown('layers') ? 'Hide' : 'Show'} Layers"
                    aria-controls="{uid}-layers"
                    onclick={(e) => toggleSection("layers", e)}
                >
                    <Layers />
                </IconButton>
                <IconButton
                    label="{shown('forms') ? 'Hide' : 'Show'} {formsName}"
                    aria-controls="{uid}-forms"
                    onclick={(e) => toggleSection("forms", e)}
                >
                    <Document />
                </IconButton>
            </div>
        {/if}
        <div id="{uid}-right-panels" class="right-panels" hidden={!rightShown}>
            <section
                id="{uid}-layers"
                aria-labelledby="{uid}-layers-title"
                hidden={!narrow && !expanded.layers}
            >
                <h2
                    id="{uid}-layers-title"
                    tabindex="-1"
                    class="px-4 pt-3 pb-2 text-heading-compact-01 text-text-primary"
                >
                    Layers
                </h2>
            </section>
            <section
                id="{uid}-forms"
                aria-labelledby="{uid}-forms-title"
                hidden={!narrow && !expanded.forms}
            >
                <h2
                    id="{uid}-forms-title"
                    class="px-4 pt-3 pb-2 text-heading-compact-01 text-text-primary"
                >
                    {formsName}
                </h2>
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
        grid-template-rows: 48px 32px minmax(0, 1fr) auto;
        grid-template-areas:
            "header header header header"
            "rail left tools right"
            "rail left canvas right"
            "rail left pager right";
    }
    .rail {
        grid-area: rail;
        display: flex;
        flex-direction: column;
        overflow-y: auto;
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
