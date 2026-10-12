import type { CarbonIconProps } from "carbon-icons-svelte";
import Archive from "carbon-icons-svelte/lib/Archive.svelte";
import CheckmarkFilled from "carbon-icons-svelte/lib/CheckmarkFilled.svelte";
import CircleDash from "carbon-icons-svelte/lib/CircleDash.svelte";
import InProgress from "carbon-icons-svelte/lib/InProgress.svelte";
import StopOutline from "carbon-icons-svelte/lib/StopOutline.svelte";
import type { Component } from "svelte";
import type { TaskState } from "../../types/openapi_types";

type Status = {
    label: string;
    icon: Component<CarbonIconProps>;
    iconClass: string;
};

// The only display text for a task state. Full class strings, so Tailwind emits them;
// a new TaskState in the OpenAPI types fails `npm run check` here.
export const TASK_STATUS: Record<TaskState, Status> = {
    NotStarted: {
        label: "Not started",
        icon: CircleDash,
        iconClass: "text-status-gray",
    },
    Busy: {
        label: "In progress",
        icon: InProgress,
        iconClass: "text-status-blue",
    },
    Finished: {
        label: "Finished",
        icon: CheckmarkFilled,
        iconClass: "text-status-green",
    },
    Aborted: {
        label: "Aborted",
        icon: StopOutline,
        iconClass: "text-status-gray",
    },
    Archived: {
        label: "Archived",
        icon: Archive,
        iconClass: "text-status-gray",
    },
};

export const TASK_STATES = Object.keys(TASK_STATUS) as TaskState[];
