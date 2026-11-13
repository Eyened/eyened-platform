import { SvelteMap, SvelteSet } from "svelte/reactivity";
import type { GridLayers } from "$lib/layers/gridLayers.svelte";
import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import { instanceIdFromImageId } from "$lib/viewer-window/viewerViewState";
import {
    DEFAULT_PRESET_ID,
    getPreset,
    smallestRowFor,
    type Preset,
} from "./presets";
import {
    changePreset,
    fillPage,
    frameSetNeighbour,
    pageCount as countPages,
    pruneSlots,
    sortCatalogue,
    swapSlots,
    type ArrangeOrder,
    type Axis,
    type CatalogueEntry,
    type LocalizerMode,
    type Slot,
} from "./workspaceRules";
import type { WorkspaceUrlState } from "./workspaceUrl";
import {
    toolById,
    type ToolGroup,
    type ToolId,
    type ToolMode,
} from "./tools/registry";

export interface WorkspaceOptions {
    /** Receives the URL state after every change; the loader passes workspaceUrl's writer. */
    writeUrl?: (state: WorkspaceUrlState) => void;
    /** Whether the thumbnail strip starts on; on when missing. */
    strip?: boolean;
    /** Whether strip tiles start following the crosshair; on when missing. */
    stripTracking?: boolean;
    /** Which localizer lines strip tiles start with; All when missing. */
    stripLocalizer?: LocalizerMode;
    /** The palette's mode; All tools when missing. */
    toolMode?: ToolMode;
}

/** What Layers acts on: one viewport's viewer, its segmentation state and its layer state. */
export interface LayersTarget {
    readonly viewerContext: ViewerContext;
    readonly mainViewerContext: MainViewerContext;
    /** ETDRS grids state, kept while Layers remounts its sections. */
    readonly grids: GridLayers;
}

/** What the palette and the options bar need from one viewport. */
export interface ViewportHandle {
    /** Screen pixels per image pixel, in percent. */
    readonly zoomPercent: number;
    zoomBy(factor: number): void;
    reset(): void;
    /** The viewport's layers; Layers lists them while it is selected. */
    readonly layers?: LayersTarget;
}

/** The state of one viewer window: the catalogue, the slots and how they page. Positions are 0-based. */
export class Workspace {
    /** Open images, sorted by `arrange`. */
    entries: CatalogueEntry[] = $state.raw([]);
    /** Whether the thumbnail strip shows above the grid. */
    strip = $state(true);
    /** Whether strip tiles follow the crosshair: tile cursor, twin zoom and OCT tile slice. */
    stripTracking = $state(true);
    /** Which localizer lines strip tiles draw. */
    stripLocalizer: LocalizerMode = $state("all");
    /** True while an open image has B-scan positions to draw; the viewer window sets it. */
    hasLocalizers = $state(false);
    arrange: ArrangeOrder = $state("opened");
    preset: Preset = $state.raw(getPreset(DEFAULT_PRESET_ID)!);
    page = $state(1);
    slots: Slot[] = $state.raw([{ id: 0, imageId: null }]);
    colSizes: number[] = $state.raw([1]);
    rowSizes: number[] = $state.raw([1]);
    selected = $state(0);
    maximised: number | null = $state(null);
    /** False until `hydrate` has run; viewports say "Loading images…" until then. */
    loaded = $state(false);
    /** Text for the polite live region. */
    announcement = $state("");
    /** The armed palette tool; null is No tool. */
    armedTool: ToolId | null = $state(null);
    /** Each job's last picked tool, shown by its slot when the rail is short. */
    lastPick: Record<ToolGroup, ToolId> = $state({
        View: "zoom",
        Measure: "distance",
        Draw: "brush",
        Place: "point",
    });
    toolMode: ToolMode = $state("all");

    catalogue = $derived(this.entries.map((e) => e.imageId));
    pageCount = $derived(countPages(this.catalogue.length, this.slots.length));
    /** More images than the slots show. */
    showPager = $derived(this.catalogue.length > this.slots.length);
    pagerText = $derived.by(() => {
        const n = this.catalogue.length;
        const first = Math.min((this.page - 1) * this.slots.length + 1, n);
        const last = Math.min(this.page * this.slots.length, n);
        return `Images ${first}–${last} of ${n}`;
    });

    private readonly viewports = new SvelteMap<number, ViewportHandle>();
    /** The selected viewport's handle; null while it is empty. */
    selectedViewport = $derived(this.viewports.get(this.selected) ?? null);

    private nextId = 1;
    /** True once the grader (or the URL) named a layout; only then is it carried to the next set. */
    private layoutChosen = false;
    private sliceIndex: Record<string, number> = {};
    /** Images whose B-scan the grader locked; kept until reload, like the remembered slice. */
    private readonly lockedIds = new SvelteSet<string>();
    /** Open images in the order they were opened; every Arrange sort starts from it. */
    // ASSUMPTION: sorts start from the opened list, so ties keep the opened order (plan decision 17).
    private opened: CatalogueEntry[] = [];
    private readonly writeUrl: ((state: WorkspaceUrlState) => void) | undefined;

    constructor(options: WorkspaceOptions = {}) {
        this.writeUrl = options.writeUrl;
        this.strip = options.strip ?? true;
        this.stripTracking = options.stripTracking ?? true;
        this.stripLocalizer = options.stripLocalizer ?? "all";
        this.toolMode = options.toolMode ?? "all";
    }

    /** The first state once the catalogue has loaded: v= wins, then a named layout, then one viewport with the first image. */
    hydrate(entries: readonly CatalogueEntry[], url: WorkspaceUrlState): void {
        this.arrange = url.arrange;
        this.opened = [...entries];
        this.entries = sortCatalogue(this.opened, url.arrange);
        const v = url.v.map((e) =>
            e && this.catalogue.includes(e.id) ? e : null,
        );
        for (const e of v) {
            if (e?.index !== undefined) this.sliceIndex[e.id] = e.index;
        }
        const named = url.layout ? getPreset(url.layout) : undefined;
        this.layoutChosen = named !== undefined;
        if (v.some((e) => e !== null)) {
            this.reset(named ?? smallestRowFor(v.length).presets[0]);
            this.slots = this.slots.map((slot, i) => ({
                id: slot.id,
                imageId: v[i]?.id ?? null,
            }));
            this.page = Math.min(url.page, this.pageCount);
        } else if (named) {
            this.reset(named);
            this.applyPreset(named);
            this.fill(Math.min(url.page, this.pageCount));
        } else {
            this.reset(getPreset(DEFAULT_PRESET_ID)!);
            this.fill(1);
        }
        this.persist();
        this.loaded = true;
    }

    setPreset(id: string): void {
        const preset = getPreset(id);
        if (!preset) return;
        this.layoutChosen = true;
        this.applyPreset(preset);
        this.announcePage();
        this.persist();
    }

    turnPage(page: number): void {
        const next = Math.min(Math.max(page, 1), this.pageCount);
        if (next === this.page) return;
        this.fill(next);
        this.announcePage();
        this.persist();
    }

    load(position: number, imageId: string): void {
        this.setSlot(position, imageId);
    }

    close(position: number): void {
        this.setSlot(position, null);
    }

    swap(a: number, b: number): void {
        if (a === b || !this.slots[a] || !this.slots[b]) return;
        this.slots = swapSlots(this.slots, a, b);
        this.announcement = `Viewports ${a + 1} and ${b + 1} swapped`;
        this.persist();
    }

    setArrange(order: ArrangeOrder): void {
        this.arrange = order;
        this.entries = sortCatalogue(this.opened, order);
        this.fill(1);
        this.announcePage();
        this.persist();
    }

    select(position: number): void {
        this.selected = position;
    }

    toggleMaximise(position: number): void {
        this.maximised = this.maximised === position ? null : position;
    }

    setMaximised(position: number): void {
        this.maximised = position;
    }

    setTracks(axis: Axis, sizes: number[]): void {
        if (axis === "col") this.colSizes = sizes;
        else this.rowSizes = sizes;
    }

    /** Previous / Next FrameSet for the selected viewport. */
    stepFrameSet(delta: 1 | -1): void {
        const imageId = this.slots[this.selected]?.imageId;
        if (!imageId) return;
        const next = frameSetNeighbour(this.entries, imageId, delta);
        if (next) this.load(this.selected, next);
    }

    /** A changed instance set: slots showing an image that left become empty. */
    prune(instanceIds: readonly string[]): void {
        const keep = (imageId: string) =>
            instanceIds.includes(instanceIdFromImageId(imageId));
        this.opened = this.opened.filter((e) => keep(e.imageId));
        this.entries = this.entries.filter((e) => keep(e.imageId));
        const { slots, emptied } = pruneSlots(this.slots, keep);
        if (emptied === 0) return;
        this.slots = slots;
        this.announcement = `${emptied} ${emptied === 1 ? "viewport" : "viewports"} emptied`;
        this.persist();
    }

    /** Appended to the opened order and sorted into the catalogue; the current page refills only on the next page turn. */
    addImages(entries: readonly CatalogueEntry[]): void {
        const fresh = entries.filter(
            (e) => !this.catalogue.includes(e.imageId),
        );
        if (!fresh.length) return;
        this.opened = [...this.opened, ...fresh];
        this.entries = sortCatalogue(this.opened, this.arrange);
    }

    peekIndex(imageId: string, depth: number): number | undefined {
        const index = this.sliceIndex[imageId];
        return index !== undefined && depth > 1 && index < depth
            ? index
            : undefined;
    }

    recordIndex(imageId: string, index: number, depth: number): void {
        if (
            depth <= 1 ||
            !Number.isInteger(index) ||
            index < 0 ||
            index >= depth
        )
            return;
        if (this.sliceIndex[imageId] === index) return;
        this.sliceIndex[imageId] = index;
        if (this.slots.some((slot) => slot.imageId === imageId)) this.persist();
    }

    isLocked(imageId: string): boolean {
        return this.lockedIds.has(imageId);
    }

    setLocked(imageId: string, on: boolean): void {
        if (on) this.lockedIds.add(imageId);
        else this.lockedIds.delete(imageId);
    }

    /** A key or a menu pick: arms a modal tool; Reset view, the one action, resets the selected viewport. */
    arm(id: ToolId): void {
        const tool = toolById(id);
        if (tool.kind === "action") {
            this.selectedViewport?.reset();
            return;
        }
        this.armedTool = id;
        this.lastPick = { ...this.lastPick, [tool.group]: id };
    }

    /** A palette click: the armed tool again returns to No tool. */
    toggleTool(id: ToolId): void {
        if (this.armedTool === id) this.armedTool = null;
        else this.arm(id);
    }

    /** A viewport's viewer registers its handle; the returned function removes it. */
    attachViewport(position: number, handle: ViewportHandle): () => void {
        this.viewports.set(position, handle);
        return () => {
            if (this.viewports.get(position) === handle)
                this.viewports.delete(position);
        };
    }

    urlState(): WorkspaceUrlState {
        return {
            v: this.slots.map((slot) => {
                if (slot.imageId === null) return null;
                const index = this.sliceIndex[slot.imageId];
                return index === undefined
                    ? { id: slot.imageId }
                    : { id: slot.imageId, index };
            }),
            layout: this.layoutChosen ? this.preset.id : null,
            page: this.page,
            arrange: this.arrange,
        };
    }

    private reset(preset: Preset): void {
        this.preset = preset;
        this.slots = preset.cells.map(() => ({
            id: this.nextId++,
            imageId: null,
        }));
        this.colSizes = [...preset.cols];
        this.rowSizes = [...preset.rows];
        this.page = 1;
        this.selected = 0;
        this.maximised = null;
    }

    private applyPreset(preset: Preset): void {
        const change = changePreset({
            slots: this.slots,
            selected: this.selected,
            catalogue: this.catalogue,
            preset,
            newId: () => this.nextId++,
        });
        this.preset = preset;
        this.slots = change.slots;
        this.page = change.page;
        this.selected = change.selected;
        this.colSizes = [...preset.cols];
        this.rowSizes = [...preset.rows];
        // ASSUMPTION: a preset change ends maximise (plan decision 8).
        this.maximised = null;
    }

    private fill(page: number): void {
        this.page = page;
        this.slots = fillPage(this.slots, this.catalogue, page);
    }

    private setSlot(position: number, imageId: string | null): void {
        this.slots = this.slots.map((slot, i) =>
            i === position ? { id: slot.id, imageId } : slot,
        );
        this.persist();
    }

    private announcePage(): void {
        const n = this.catalogue.length;
        const u = this.slots.length;
        if (n === 0) {
            this.announcement = "Page 1 of 1";
            return;
        }
        const first = (this.page - 1) * u + 1;
        const last = Math.min(this.page * u, n);
        this.announcement = `Page ${this.page} of ${this.pageCount}, images ${first}–${last}`;
    }

    private persist(): void {
        this.writeUrl?.(this.urlState());
    }
}
