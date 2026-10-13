import type { CarbonIconProps } from "carbon-icons-svelte";
import CheckmarkFilled from "carbon-icons-svelte/lib/CheckmarkFilled.svelte";
import CircleDash from "carbon-icons-svelte/lib/CircleDash.svelte";
import Incomplete from "carbon-icons-svelte/lib/Incomplete.svelte";
import InProgress from "carbon-icons-svelte/lib/InProgress.svelte";
import UndefinedFilled from "carbon-icons-svelte/lib/UndefinedFilled.svelte";
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
        icon: Incomplete,
        iconClass: "text-status-blue",
    },
    Archived: {
        label: "Archived",
        icon: UndefinedFilled,
        iconClass: "text-status-purple",
    },
};

export const TASK_STATES = Object.keys(TASK_STATUS) as TaskState[];
