import type { Component } from "svelte";
import type { PanelName } from "$lib/viewer/viewer-utils";
import type { FormSchemaGET } from "../../types/openapi_types";
import type { QuickFormPanelConfig, TaskConfig } from "./taskConfigLayout";
import PanelInfo from "./panelInfo/panelInfo.svelte";
import PanelRendering from "./panelRendering/PanelRendering.svelte";
import PanelETDRS from "./panelETRDS/PanelETDRS.svelte";
import PanelRegistration from "./panelRegistration/PanelRegistration.svelte";
import PanelMeasure from "./panelMeasure/PanelMeasure.svelte";
import PanelForm from "./panelForm/PanelForm.svelte";
import PanelSegmentation from "./panelSegmentation/PanelSegmentation.svelte";
import PanelQuickForm from "./panelQuickForm/PanelQuickForm.svelte";
import {
    Draw,
    ETDRS,
    Form,
    Info,
    Registration,
    Rendering,
} from "./icons/icons";
import Measure from "./icons/Measure.svelte";
import InfoPanelHelp from "./panelHelp/InfoPanelHelp.svelte";
import RenderingPanelHelp from "./panelHelp/RenderingPanelHelp.svelte";
import EtdrsPanelHelp from "./panelHelp/EtdrsPanelHelp.svelte";
import RegistrationPanelHelp from "./panelHelp/RegistrationPanelHelp.svelte";
import MeasurePanelHelp from "./panelHelp/MeasurePanelHelp.svelte";
import FormPanelHelp from "./panelHelp/FormPanelHelp.svelte";
import SegmentationPanelHelp from "./panelHelp/SegmentationPanelHelp.svelte";

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
        {
            name: "Rendering",
            component: PanelRendering,
            Icon: Rendering,
            Help: RenderingPanelHelp,
        },
    ];

    if (input.is2D && input.etdrsSchema) {
        panels.push({
            name: "ETDRS",
            component: PanelETDRS,
            Icon: ETDRS,
            Help: EtdrsPanelHelp,
            props: { etdrsSchema: input.etdrsSchema, active: false },
        });
    }

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

    panels.push(
        {
            name: "Measure",
            component: PanelMeasure,
            Icon: Measure,
            Help: MeasurePanelHelp,
            props: { active: false },
        },
        { name: "Form", component: PanelForm, Icon: Form, Help: FormPanelHelp },
        {
            name: "Segmentation",
            component: PanelSegmentation,
            Icon: Draw,
            Help: SegmentationPanelHelp,
        },
    );

    return panels;
}

function resolveCustomPanel(config: QuickFormPanelConfig): ResolvedPanel | null {
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
