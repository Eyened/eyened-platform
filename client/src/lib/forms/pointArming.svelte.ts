import type { PointMarkerStyle } from "$lib/config/clientDefaults";
import type { PointAdapter } from "$lib/forms/pointAdapters";
import type { PointSchemaAnalysis } from "$lib/forms/pointSchema";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";

export type PointSlotKey = {
    index: number;
    key: string;
    label: string;
};

type PointSessionBase = {
    key: string;
    canEdit: boolean;
    pointStyle: PointMarkerStyle;
    radius: number;
    color: string;
    /** If set, only this viewer mounts the tool; if omitted, every MainViewer mounts. */
    host?: ViewerContext;
    slotKeys?: readonly PointSlotKey[];
    /** When true, empty click uses placePointAt(activeSlot). Default: !!slotKeys?.length */
    useActiveSlotPlacement?: boolean;
    /** Optional display label for the tool/marker (e.g. the schema field title). */
    label?: string;
};

export type PointSession = PointSessionBase &
    (
        | {
              /** Panels: adapter already bound to FormData (+ fixed getPublicId). */
              adapter: PointAdapter;
              fieldBinding?: never;
          }
        | {
              adapter?: never;
              /**
               * Form path: each MainViewer builds a FieldAdapter with that viewer's PublicID.
               */
              fieldBinding: {
                  analysis: PointSchemaAnalysis;
                  getFieldValue: () => unknown;
                  setFieldValue: (next: unknown) => void;
              };
          }
    );

class PointArming {
    session: PointSession | null = $state(null);
    activeSlot: number = $state(0);

    /**
     * Arm a new session. Same key + same host toggles the session off
     * (re-click to disarm). Same key + different host replaces the current
     * session rather than toggling it off, so arming keys can collide across
     * viewers (e.g. the same annotation open in two MainViewers) without one
     * viewer's click silently disarming another viewer's tool.
     */
    arm(session: PointSession): void {
        if (
            this.session?.key === session.key &&
            this.session?.host === session.host
        ) {
            this.disarm();
            return;
        }
        this.session = session;
        this.activeSlot = 0;
    }

    disarm(key?: string): void {
        if (key && this.session?.key !== key) return;
        this.session = null;
    }

    setActiveSlot(index: number): void {
        this.activeSlot = Math.max(0, index);
    }

    isArmed(key: string): boolean {
        return this.session?.key === key;
    }
}

export const pointArming = new PointArming();
