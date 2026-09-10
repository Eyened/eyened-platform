export type QuickFormPanelConfig = {
    type: "quick-form";
    title: string;
    expanded?: boolean;
};

export type ClientConfigLayout = {
    hide: string[];
    prepend: QuickFormPanelConfig[];
};

/** Viewer point-tool marker appearance (Form / Registration; ETDRS hardcodes its own). */
export type PointMarkerStyle = "circle" | "cross" | "rect";

export type PointMarkerConfig = {
    style: PointMarkerStyle;
    radius: number;
    /** CSS color for marker stroke/fill (e.g. "rgba(0, 255, 0, 1)"). */
    color: string;
};

export type ClientConfig = {
    form_schema_name?: string;
    update_subtask_image_links: boolean;
    layout: ClientConfigLayout;
    point_marker: PointMarkerConfig;
};

export const CLIENT_DEFAULTS: ClientConfig = {
    update_subtask_image_links: false,
    layout: { hide: [], prepend: [] },
    point_marker: {
        style: "cross",
        radius: 16,
        color: "rgba(0, 255, 0, 1)",
    },
};

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isQuickFormPanel(value: unknown): value is QuickFormPanelConfig {
    if (!isRecord(value)) return false;
    return (
        value.type === "quick-form" &&
        typeof value.title === "string" &&
        (value.expanded === undefined || typeof value.expanded === "boolean")
    );
}

function isPointMarkerStyle(value: unknown): value is PointMarkerStyle {
    return value === "circle" || value === "cross" || value === "rect";
}

export function mergeClientConfig(
    defaults: ClientConfig,
    override: unknown,
): ClientConfig {
    if (!isRecord(override)) {
        return {
            ...defaults,
            layout: {
                hide: [...defaults.layout.hide],
                prepend: [...defaults.layout.prepend],
            },
            point_marker: { ...defaults.point_marker },
        };
    }

    const next: ClientConfig = {
        ...defaults,
        layout: {
            hide: [...defaults.layout.hide],
            prepend: [...defaults.layout.prepend],
        },
        point_marker: { ...defaults.point_marker },
    };

    if (typeof override.form_schema_name === "string") {
        next.form_schema_name = override.form_schema_name;
    }
    if (typeof override.update_subtask_image_links === "boolean") {
        next.update_subtask_image_links = override.update_subtask_image_links;
    }

    if (isRecord(override.layout)) {
        const layout = override.layout;
        if (Array.isArray(layout.hide)) {
            next.layout.hide = layout.hide.filter(
                (x): x is string => typeof x === "string",
            );
        }
        if (Array.isArray(layout.prepend)) {
            next.layout.prepend = layout.prepend.filter(isQuickFormPanel);
        }
    }

    if (isRecord(override.point_marker)) {
        const pm = override.point_marker;
        if (isPointMarkerStyle(pm.style)) {
            next.point_marker.style = pm.style;
        }
        if (
            typeof pm.radius === "number" &&
            Number.isFinite(pm.radius) &&
            pm.radius > 0
        ) {
            next.point_marker.radius = pm.radius;
        }
        if (typeof pm.color === "string" && pm.color.length > 0) {
            next.point_marker.color = pm.color;
        }
    }

    return next;
}
