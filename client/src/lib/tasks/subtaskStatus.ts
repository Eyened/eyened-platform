import CheckmarkFilled from "carbon-icons-svelte/lib/CheckmarkFilled.svelte";
import CircleDash from "carbon-icons-svelte/lib/CircleDash.svelte";
import InProgress from "carbon-icons-svelte/lib/InProgress.svelte";
import type { SubTaskState } from "../../types/openapi_types";
import type { Status } from "./taskStatus";

// The only display text for a subtask state (Carbon IconIndicator kinds). Full class strings,
// so Tailwind emits them; a new SubTaskState in the OpenAPI types fails `npm run check` here.
export const SUBTASK_STATUS: Record<SubTaskState, Status> = {
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
    Ready: {
        label: "Ready",
        icon: CheckmarkFilled,
        iconClass: "text-status-green",
    },
};

export const SUBTASK_STATES = Object.keys(SUBTASK_STATUS) as SubTaskState[];
