import type { PanelName } from "$lib/viewer/viewer-utils";

export type QuickFormPanelConfig = {
    type: "quick-form";
    title: string;
    expanded?: boolean;
};

export type TaskConfigLayout = {
    hide?: PanelName[];
    prepend?: QuickFormPanelConfig[];
};

export type TaskConfig = {
    form_schema_name?: string;
    form_image_scope?: boolean;
    layout?: TaskConfigLayout;
    [key: string]: unknown;
};

export function isTaskConfigLayout(value: unknown): value is TaskConfigLayout {
    return typeof value === "object" && value !== null;
}
