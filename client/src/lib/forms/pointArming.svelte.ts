import type { PointMarkerStyle } from "$lib/config/clientDefaults";
import {
    getPointsForImage,
    setPointsForImage,
    type PointList,
    type PointSchemaAnalysis,
} from "$lib/forms/pointSchema";

/**
 * Form PointField arming — while armed, `fieldValue` is the live source of
 * truth shared by PointTool(s) and PointField. Form `value` / server are
 * updated via `persist()` (pointerup, PointField edits, disarm).
 */
export class FormPointSession {
    readonly key: string;
    readonly canEdit: boolean;
    readonly pointStyle: PointMarkerStyle;
    readonly radius: number;
    readonly color: string;
    readonly label: string | undefined;
    readonly analysis: PointSchemaAnalysis;
    private readonly setFieldValue: (next: unknown) => void;

    /** Live field JSON while armed (bare list or by-image map). */
    fieldValue = $state<unknown>(undefined);

    constructor(args: {
        key: string;
        canEdit: boolean;
        pointStyle: PointMarkerStyle;
        radius: number;
        color: string;
        label?: string;
        analysis: PointSchemaAnalysis;
        initialValue: unknown;
        setFieldValue: (next: unknown) => void;
    }) {
        this.key = args.key;
        this.canEdit = args.canEdit;
        this.pointStyle = args.pointStyle;
        this.radius = args.radius;
        this.color = args.color;
        this.label = args.label;
        this.analysis = args.analysis;
        this.setFieldValue = args.setFieldValue;
        this.fieldValue = args.initialValue;
    }

    getPoints(publicId: string): PointList {
        return getPointsForImage(this.fieldValue, publicId, this.analysis);
    }

    setPoints(publicId: string, points: PointList) {
        this.fieldValue = setPointsForImage(
            this.fieldValue,
            publicId,
            points,
            this.analysis,
        );
    }

    /** Write live value into the form (triggers debounced server save). */
    persist() {
        this.setFieldValue(this.fieldValue);
    }
}

class PointArming {
    session: FormPointSession | null = $state(null);

    arm(session: FormPointSession) {
        if (this.session?.key === session.key) {
            this.disarm();
            return;
        }
        this.session?.persist();
        this.session = session;
    }

    disarm(key?: string) {
        if (key && this.session?.key !== key) return;
        this.session?.persist();
        this.session = null;
    }

    isArmed(key: string) {
        return this.session?.key === key;
    }
}

export const pointArming = new PointArming();
