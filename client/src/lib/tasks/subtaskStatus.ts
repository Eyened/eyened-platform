import CheckmarkFilled from "carbon-icons-svelte/lib/CheckmarkFilled.svelte";
import CircleDash from "carbon-icons-svelte/lib/CircleDash.svelte";
import InProgress from "carbon-icons-svelte/lib/InProgress.svelte";
import type { SubTaskState } from "../../types/openapi_types";
import type { Status } from "./taskStatus";

// The only display text for a subtask state (Carbon IconIndicator kinds), and what it means in the
// header's Set status menu. Full class strings, so Tailwind emits them; a new SubTaskState in the
// OpenAPI types fails `npm run check` here.
export const SUBTASK_STATUS: Record<
    SubTaskState,
    Status & { description: string }
> = {
    NotStarted: {
        label: "Not started",
        icon: CircleDash,
        iconClass: "text-status-gray",
        description: "You haven't begun grading this set.",
    },
    Busy: {
        label: "In progress",
        icon: InProgress,
        iconClass: "text-status-blue",
        description: "You've started; come back to finish it.",
    },
    Ready: {
        label: "Ready",
        icon: CheckmarkFilled,
        iconClass: "text-status-green",
        description:
            "You're done with this set. It counts as ready in the Task overview.",
    },
};

export const SUBTASK_STATES = Object.keys(SUBTASK_STATUS) as SubTaskState[];
