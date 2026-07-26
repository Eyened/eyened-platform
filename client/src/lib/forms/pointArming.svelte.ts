import type { PointMarkerStyle } from "$lib/config/clientDefaults";
import type { PointSchemaAnalysis } from "$lib/forms/pointSchema";

/** Panel-owned tools (ETDRS / Registration) — caller attaches overlays and returns dispose. */
type PanelArmed = {
    kind: "panel";
    key: string;
    dispose: () => void;
};

/**
 * Form PointField arming — MainViewers each mount a PointTool that reads/writes
 * through these accessors (one destination, many viewer hosts).
 */
export type FormPointArming = {
    kind: "form";
    key: string;
    analysis: PointSchemaAnalysis;
    label: string;
    canEdit: boolean;
    pointStyle: PointMarkerStyle;
    radius: number;
    color: string;
    getFieldValue: () => unknown;
    setFieldValue: (next: unknown) => void;
};

type Armed = PanelArmed | FormPointArming;

class PointArming {
    armed: Armed | null = $state(null);

    /** Panel pattern: attach overlays now; dispose on disarm / replace. */
    arm(key: string, attach: () => () => void) {
        if (this.armed?.key === key) {
            this.disarm();
            return;
        }
        this.disarm();
        this.armed = { kind: "panel", key, dispose: attach() };
    }

    /** Form pattern: publish target; MainViewers mount tools reactively. */
    armForm(target: Omit<FormPointArming, "kind">) {
        if (this.armed?.key === target.key) {
            this.disarm();
            return;
        }
        this.disarm();
        this.armed = { kind: "form", ...target };
    }

    /** Reactive form target for MainViewer effects (null if panel-armed or idle). */
    get formTarget(): FormPointArming | null {
        return this.armed?.kind === "form" ? this.armed : null;
    }

    disarm(key?: string) {
        if (key && this.armed?.key !== key) return;
        if (this.armed?.kind === "panel") {
            this.armed.dispose();
        }
        this.armed = null;
    }

    isArmed(key: string) {
        return this.armed?.key === key;
    }
}

export const pointArming = new PointArming();
