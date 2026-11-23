import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { Workspace } from "$lib/workspace/workspace.svelte";
import type { FormTarget } from "./formTargets";

/** The viewer the form window's point fields use: the selected viewport if it shows the target, else the first that does. */
export function viewerFor(
    workspace: Workspace,
    target: FormTarget,
): ViewerContext | undefined {
    const shows = (position: number) => {
        const id = workspace.slots[position]?.imageId;
        return id != null && target.imageIds.includes(id);
    };
    const position = shows(workspace.selected)
        ? workspace.selected
        : workspace.slots.findIndex((_, p) => shows(p));
    return position === -1
        ? undefined
        : workspace.handleAt(position)?.layers?.viewerContext;
}
