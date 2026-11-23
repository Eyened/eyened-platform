import type { LayerSectionId } from "$lib/layers/layerSections";
import type { Segmentation } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";

export type SaveState = "synced" | "saving" | "error";

/** What the header calls a failed save: "1 segmentation couldn't save". */
export type SaveKind =
    | "form"
    | "registration"
    | "ETDRS grid"
    | "segmentation"
    | "status";

/** The Layers item a Retry belongs to; grid and pointset have the shape of a Layers selection. */
export type RevealItem =
    | { kind: "segmentation"; segmentation: Segmentation }
    | { kind: "grid"; id: number }
    | { kind: "pointset"; id: number };

/** Where a saver's Retry is: a Layers item in a viewport that shows `imageId`, or something to focus. */
export type RevealTarget =
    | {
          to: "layers";
          section: LayerSectionId;
          imageId: string;
          item: RevealItem;
      }
    | { to: "focus"; focus: () => void };

export interface Saver {
    readonly kind: SaveKind;
    /** One item in the header count: a segmentation's B-scans and its threshold share it. */
    readonly group: string;
    readonly target: RevealTarget;
    readonly state: SaveState;
    /** Sends what waits now, also after an error (Retry); resolves when nothing is in flight. */
    flush(): Promise<void>;
}

const NOUNS: Record<Exclude<SaveKind, "status">, [string, string]> = {
    form: ["form", "forms"],
    registration: ["registration", "registrations"],
    "ETDRS grid": ["ETDRS grid", "ETDRS grids"],
    segmentation: ["segmentation", "segmentations"],
};

/** An error beats a save in progress, which beats saved. */
export function worstState(savers: readonly Saver[]): SaveState {
    if (savers.some((s) => s.state === "error")) return "error";
    if (savers.some((s) => s.state === "saving")) return "saving";
    return "synced";
}

/** Every background save on the page; each set is a page load, so one per page. */
export class SaveTracker {
    savers: Saver[] = $state.raw([]);
    /** False until the first edit on the page; the header shows nothing before it. */
    edited = $state(false);
    /** A move that leaves on purpose, so the browser doesn't ask "Leave site?". */
    leaving = false;
    /** Set by the workspace frame, the one place that can open Layers. */
    revealer:
        | ((target: Extract<RevealTarget, { to: "layers" }>) => void)
        | null = null;
    private installed = false;

    readonly worst = $derived(worstState(this.savers));

    readonly text = $derived.by(() => {
        if (!this.edited) return "";
        // One entry per group, so a segmentation's B-scans count once.
        const failed = this.savers
            .filter((saver) => saver.state === "error")
            .filter(
                (saver, i, all) =>
                    all.findIndex((other) => other.group === saver.group) === i,
            );
        if (failed.length === 0)
            return this.worst === "saving" ? "Saving…" : "Saved";
        const kinds = failed
            .map((saver) => saver.kind)
            .filter((kind, i, all) => all.indexOf(kind) === i);
        if (kinds.length > 1) return `${failed.length} items couldn't save`;
        const kind = kinds[0]!;
        if (kind === "status") return "Status couldn't save";
        const [one, many] = NOUNS[kind];
        return `${failed.length} ${failed.length === 1 ? one : many} couldn't save`;
    });

    join(saver: Saver): () => void {
        this.install();
        this.savers = [...this.savers, saver];
        return () => {
            this.savers = this.savers.filter((s) => s !== saver);
        };
    }

    /** First in join order. */
    firstUnsaved(): Saver | undefined {
        return this.savers.find((s) => s.state !== "synced");
    }

    /** Resolves when every saver is saved or failed. */
    async flushAll(): Promise<void> {
        await Promise.all(this.savers.map((s) => s.flush()));
    }

    reveal(saver: Saver): void {
        const target = saver.target;
        if (target.to === "focus") target.focus();
        else this.revealer?.(target);
    }

    private install(): void {
        if (this.installed || typeof window === "undefined") return;
        this.installed = true;
        // A hidden tab may never come back, so its saves go now.
        document.addEventListener("visibilitychange", () => {
            if (document.visibilityState === "hidden") void this.flushAll();
        });
        // Closing with unsaved work: the browser's own "Leave site?".
        window.addEventListener("beforeunload", (event) => {
            if (this.leaving || !this.firstUnsaved()) return;
            event.preventDefault();
            event.returnValue = "";
        });
    }
}

export const saveTracker = new SaveTracker();
