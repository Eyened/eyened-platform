<!--
@component
The viewer's region grid: header, left icon column and panel, tool options bar, canvas, pager and right column.
-->
<script lang="ts">
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import Document from "carbon-icons-svelte/lib/Document.svelte";
    import Help from "carbon-icons-svelte/lib/Help.svelte";
    import Image from "carbon-icons-svelte/lib/Image.svelte";
    import Information from "carbon-icons-svelte/lib/Information.svelte";
    import Layers from "carbon-icons-svelte/lib/Layers.svelte";
    import { getContext, tick, type Snippet } from "svelte";
    import { MediaQuery } from "svelte/reactivity";
    import type { ViewportTitle } from "./imageMeta";
    import ImagesListShell from "./ImagesListShell.svelte";
    import Pager from "./Pager.svelte";
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

    const storedLeft = readLeftPanel();
    // Images starts closed while the strip is on: the strip already shows the catalogue.
    // ASSUMPTION: read once at mount (plan decision 22).
    const defaultLeft: LeftPanel | null = workspace.strip ? null : "images";
    let left: LeftPanel | null = $state(
        md.current
            ? storedLeft === undefined
                ? defaultLeft
                : storedLeft
            : null,
    );
    let rightChoice: boolean | undefined = $state(readRightOpen());
    // The user's choice beats the narrow-window default.
    const rightOpen = $derived(rightChoice ?? xlg.current);
    let expanded = $state({ layers: true, forms: true });
    const formsName = $derived(task ? "Grading" : "Forms");
    const overlayOpen = $derived(narrow && (left !== null || rightOpen));
    let opener: HTMLElement | null = null;

    const LEFT_PANELS = [
        { id: "images", label: "Images", Icon: Image },
        { id: "info", label: "Info", Icon: Information },
        { id: "help", label: "Help", Icon: Help },
    ] as const;

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
        if (narrow && left && rightOpen) setRight(false);
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
        if (narrow) left = null;
    }

    function closeOverlays() {
        left = null;
        if (rightOpen) setRight(false);
    }

    function onkeydown(e: KeyboardEvent) {
        if (e.key !== "Escape" || !overlayOpen) return;
        e.preventDefault();
        closeOverlays();
        opener?.focus();
    }

    async function chooseImage() {
        left = "images";
        writeLeftPanel(left);
        await tick();
        document
            .getElementById(`${uid}-images`)
            ?.querySelector<HTMLElement>("li button")
            ?.focus();
    }

    function imageLoaded() {
        if (narrow) left = null;
    }

    // ASSUMPTION: the root <Toaster> reads these (plan decision 16): bottom right of the canvas, above the pager.
    $effect(() => {
        const style = document.body.style;
        style.setProperty(
            "--viewer-toast-right",
            `${(rightOpen && !narrow ? RIGHT_OPEN_PX : RAIL_PX) + 16}px`,
        );
        style.setProperty(
            "--viewer-toast-bottom",
            `${workspace.showPager ? 48 : 16}px`,
        );
        return () => {
            style.removeProperty("--viewer-toast-right");
            style.removeProperty("--viewer-toast-bottom");
        };
    });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
    class="frame"
    class:narrow
    style="--left: {left && !narrow ? '256px' : '0px'}; --right: {rightOpen &&
    !narrow
        ? `${RIGHT_OPEN_PX}px`
        : `${RAIL_PX}px`};"
    {onkeydown}
>
    <WorkspaceHeader {task} {narrow} />
    <nav class="rail" aria-label="Tools and panels">
        <div role="group" aria-label="Tools"></div>
        <div class="rail-bottom">
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
    <div class="left" class:open={left !== null}>
        {#each LEFT_PANELS as panel (panel.id)}
            <section
                id="{uid}-{panel.id}"
                aria-labelledby="{uid}-{panel.id}-title"
                hidden={left !== panel.id}
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
    <div class="tool-options"></div>
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
    <div class="pager"><Pager /></div>
    <aside class="right" aria-label="Layers and {formsName.toLowerCase()}">
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
        <div class="right-panels" hidden={!rightOpen}>
            <section
                id="{uid}-layers"
                aria-labelledby="{uid}-layers-title"
                hidden={!expanded.layers}
            >
                <h2
                    id="{uid}-layers-title"
                    class="px-4 pt-3 pb-2 text-heading-compact-01 text-text-primary"
                >
                    Layers
                </h2>
            </section>
            <section
                id="{uid}-forms"
                aria-labelledby="{uid}-forms-title"
                hidden={!expanded.forms}
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
        <div class="scrim" aria-hidden="true" onclick={closeOverlays}></div>
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
        grid-template-columns: 48px var(--left) minmax(0, 1fr) var(--right);
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
    .left:not(.open) {
        display: none;
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
    .narrow .left.open {
        position: absolute;
        top: 48px;
        bottom: 0;
        left: 48px;
        z-index: 20;
        width: min(256px, calc(100% - 96px));
    }
    .narrow .right-panels:not([hidden]) {
        position: absolute;
        top: 48px;
        bottom: 0;
        right: 48px;
        z-index: 20;
        width: min(240px, calc(100% - 96px));
        background: var(--color-layer-01);
    }
    .scrim {
        position: absolute;
        inset: 48px 48px 0 48px;
        z-index: 10;
        background: var(--color-overlay);
    }
</style>
