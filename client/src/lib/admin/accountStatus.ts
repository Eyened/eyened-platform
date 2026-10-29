import CheckmarkOutline from "carbon-icons-svelte/lib/CheckmarkOutline.svelte";
import UndefinedFilled from "carbon-icons-svelte/lib/UndefinedFilled.svelte";
import type { Status } from "$lib/tasks/taskStatus";
import type { AdminUserResponse } from "../../types/openapi_types";

// Carbon IconIndicator kinds: Active = normal, Inactive = undefined. Full class strings, so Tailwind emits them.
const ACTIVE: Status = {
    label: "Active",
    icon: CheckmarkOutline,
    iconClass: "text-status-blue",
};
const INACTIVE: Status = {
    label: "Inactive",
    icon: UndefinedFilled,
    iconClass: "text-status-purple",
};

export function accountStatus(user: Pick<AdminUserResponse, "active">): Status {
    return user.active ? ACTIVE : INACTIVE;
}

export const PASSWORD_HINT =
    'At least 15 characters. Must not contain the username or "eyened".';
