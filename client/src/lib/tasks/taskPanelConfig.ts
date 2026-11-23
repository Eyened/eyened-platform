export type TaskPanelSections = {
    title: boolean;
    nav: boolean;
    status: boolean;
    comments: boolean;
    overview: boolean;
};

export type TaskPanelConfig = {
    enabled: boolean;
    expanded: boolean;
    sections: TaskPanelSections;
};

const SECTION_KEYS = [
    "title",
    "nav",
    "status",
    "comments",
    "overview",
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function defaultConfig(): TaskPanelConfig {
    return {
        enabled: true,
        expanded: false,
        sections: {
            title: true,
            nav: true,
            status: true,
            comments: true,
            overview: true,
        },
    };
}

export function parseTaskPanelConfig(
    taskDefinitionConfig: unknown,
): TaskPanelConfig {
    const next = defaultConfig();
    if (!isRecord(taskDefinitionConfig)) return next;
    const raw = taskDefinitionConfig.task_panel;
    if (!isRecord(raw)) return next;

    if (typeof raw.enabled === "boolean") next.enabled = raw.enabled;
    if (typeof raw.expanded === "boolean") next.expanded = raw.expanded;

    if (isRecord(raw.sections)) {
        for (const key of SECTION_KEYS) {
            const value = raw.sections[key];
            if (typeof value === "boolean") next.sections[key] = value;
        }
    }

    return next;
}

/** What the viewer header shows for a task. With Status off and ◀ ▶ on, the primary button is only "Go to next set". */
export function taskHeaderShows(config: TaskPanelConfig) {
    const on = (key: keyof TaskPanelSections) =>
        config.enabled && config.sections[key];
    return {
        title: on("title"),
        nav: on("nav"),
        overview: on("overview"),
        status: on("status"),
        goToNext: !on("status") && on("nav"),
    };
}
