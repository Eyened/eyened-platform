import type { Component } from "svelte";
import type { PanelName } from "$lib/viewer/viewer-utils";
import type { FormSchemaGET } from "../../types/openapi_types";
import type { QuickFormPanelConfig, TaskConfig } from "./taskConfigLayout";
import PanelInfo from "./panelInfo/panelInfo.svelte";
import PanelRegistration from "./panelRegistration/PanelRegistration.svelte";
import PanelForm from "./panelForm/PanelForm.svelte";
import PanelQuickForm from "./panelQuickForm/PanelQuickForm.svelte";
import { Form, Info, Registration } from "./icons/icons";
import InfoPanelHelp from "./panelHelp/InfoPanelHelp.svelte";
import RegistrationPanelHelp from "./panelHelp/RegistrationPanelHelp.svelte";
import FormPanelHelp from "./panelHelp/FormPanelHelp.svelte";

export type ResolvedPanel = {
    name: PanelName;
    component: Component;
    Icon: Component;
    Help?: Component;
    props?: Record<string, unknown>;
};

export type BuildDefaultPanelsInput = {
    is2D: boolean;
    etdrsSchema?: FormSchemaGET;
    registrationSchema?: FormSchemaGET;
};

export type ResolvePanelsResult = {
    panels: ResolvedPanel[];
    expandedPanelNames: PanelName[];
};

const CUSTOM_PANEL_REGISTRY: Record<
    QuickFormPanelConfig["type"],
    Pick<ResolvedPanel, "component" | "Icon" | "Help">
> = {
    "quick-form": {
        component: PanelQuickForm,
        Icon: Form,
        Help: FormPanelHelp,
    },
};

export function buildDefaultPanels(
    input: BuildDefaultPanelsInput,
): ResolvedPanel[] {
    const panels: ResolvedPanel[] = [
        { name: "Info", component: PanelInfo, Icon: Info, Help: InfoPanelHelp },
    ];

    if (input.is2D && input.registrationSchema) {
        panels.push({
            name: "Registration",
            component: PanelRegistration,
            Icon: Registration,
            Help: RegistrationPanelHelp,
            props: {
                registrationSchema: input.registrationSchema,
                active: false,
            },
        });
    }

    panels.push({
        name: "Form",
        component: PanelForm,
        Icon: Form,
        Help: FormPanelHelp,
    });

    return panels;
}

function resolveCustomPanel(
    config: QuickFormPanelConfig,
): ResolvedPanel | null {
    const entry = CUSTOM_PANEL_REGISTRY[config.type];
    if (!entry) {
        console.warn(`Unknown custom panel type: ${config.type}`);
        return null;
    }
    return {
        name: config.title,
        component: entry.component,
        Icon: entry.Icon,
        Help: entry.Help,
        props: { title: config.title },
    };
}

export function resolvePanels(
    input: BuildDefaultPanelsInput,
    taskConfig?: TaskConfig,
): ResolvePanelsResult {
    let panels = buildDefaultPanels(input);
    const expandedPanelNames: PanelName[] = [];

    const layout = taskConfig?.layout;
    if (!layout) {
        return { panels, expandedPanelNames };
    }

    const hide = new Set(layout.hide ?? []);
    panels = panels.filter((panel) => !hide.has(panel.name));

    for (const config of layout.prepend ?? []) {
        const custom = resolveCustomPanel(config);
        if (!custom) continue;
        panels.unshift(custom);
        if (config.expanded) {
            expandedPanelNames.push(custom.name);
        }
    }

    return { panels, expandedPanelNames };
}
