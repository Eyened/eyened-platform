import type { PointMarkerStyle } from "$lib/config/clientDefaults";
import type { PointSchemaAnalysis } from "$lib/forms/pointSchema";

/**
 * Form PointField arming only — each MainViewer mounts a PointTool and syncs
 * via fieldBinding. Panels (ETDRS / Registration) own their tools locally.
 */
export type FormPointSession = {
    key: string;
    canEdit: boolean;
    pointStyle: PointMarkerStyle;
    radius: number;
    color: string;
    label?: string;
    analysis: PointSchemaAnalysis;
    getFieldValue: () => unknown;
    setFieldValue: (next: unknown) => void;
};

class PointArming {
    session: FormPointSession | null = $state(null);

    arm(session: FormPointSession) {
        if (this.session?.key === session.key) {
            this.disarm();
            return;
        }
        this.session = session;
    }

    disarm(key?: string) {
        if (key && this.session?.key !== key) return;
        this.session = null;
    }

    isArmed(key: string) {
        return this.session?.key === key;
    }
}

export const pointArming = new PointArming();
