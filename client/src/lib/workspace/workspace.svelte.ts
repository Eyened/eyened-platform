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
    type Slot,
} from "./workspaceRules";
import type { WorkspaceUrlState } from "./workspaceUrl";

export interface WorkspaceOptions {
    /** Receives the URL state after every change; the loader passes workspaceUrl's writer. */
    writeUrl?: (state: WorkspaceUrlState) => void;
    /** Whether the thumbnail strip starts on; on when missing. */
    strip?: boolean;
}

/** The state of one viewer window: the catalogue, the slots and how they page. Positions are 0-based. */
export class Workspace {
    /** Open images, sorted by `arrange`. */
    entries: CatalogueEntry[] = $state.raw([]);
    /** Whether the thumbnail strip shows above the grid. */
    strip = $state(true);
    arrange: ArrangeOrder = $state("opened");
    preset: Preset = $state.raw(getPreset(DEFAULT_PRESET_ID)!);
    page = $state(1);
    slots: Slot[] = $state.raw([{ id: 0, imageId: null }]);
    colSizes: number[] = $state.raw([1]);
    rowSizes: number[] = $state.raw([1]);
    selected = $state(0);
    maximised: number | null = $state(null);
    /** Text for the polite live region. */
    announcement = $state("");

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

    private nextId = 1;
    /** True once the grader (or the URL) named a layout; only then is it carried to the next set. */
    private layoutChosen = false;
    private sliceIndex: Record<string, number> = {};
    /** Open images in the order they were opened; every Arrange sort starts from it. */
    // ASSUMPTION: sorts start from the opened list, so ties keep the opened order (plan decision 17).
    private opened: CatalogueEntry[] = [];
    private readonly writeUrl: ((state: WorkspaceUrlState) => void) | undefined;

    constructor(options: WorkspaceOptions = {}) {
        this.writeUrl = options.writeUrl;
        this.strip = options.strip ?? true;
    }

    /** The first state once the catalogue has loaded: v= wins, then a named layout, then the BIR first screen. */
    hydrate(
        entries: readonly CatalogueEntry[],
        url: WorkspaceUrlState,
        pair: readonly [string, string] | null,
    ): void {
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
        } else if (pair) {
            this.reset(getPreset("2x1")!);
            this.slots = this.slots.map((slot, i) => ({
                id: slot.id,
                imageId: pair[i],
            }));
        } else {
            this.reset(getPreset(DEFAULT_PRESET_ID)!);
            this.fill(1);
        }
        this.persist();
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
