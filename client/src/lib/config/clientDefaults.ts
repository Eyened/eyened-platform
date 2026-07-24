export type QuickFormPanelConfig = {
    type: "quick-form";
    title: string;
    expanded?: boolean;
};

export type ClientConfigLayout = {
    hide: string[];
    prepend: QuickFormPanelConfig[];
};

export type ClientConfig = {
    form_schema_name?: string;
    update_subtask_image_links: boolean;
    layout: ClientConfigLayout;
};

export const CLIENT_DEFAULTS: ClientConfig = {
    update_subtask_image_links: false,
    layout: { hide: [], prepend: [] },
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
        };
    }

    const next: ClientConfig = {
        ...defaults,
        layout: {
            hide: [...defaults.layout.hide],
            prepend: [...defaults.layout.prepend],
        },
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

    return next;
}
