import { goto } from "$app/navigation";
import { ApiError, isOutOfDeclaration } from "$lib/api/client";
import type { Condition } from "$lib/browser/browserContext.svelte";
import { addSubTaskImage, removeSubTaskImage } from "$lib/data/helpers";
import { instances, subtasks } from "$lib/data/stores.svelte";

const NOT_APPLIED = "Earlier changes were saved; the rest were not applied.";

export interface AddImagesTarget {
    /** The set whose image links to save; null outside a task or with "Save to the set's images" off. */
    subTaskId: number | null;
    setInstanceIDs: (ids: string[]) => unknown;
    /** /view: the address keeps the open images in instances=. */
    rewriteUrl: boolean;
}

/** Saves the set's links when asked, then opens the images. It resolves once the links are saved, so the modal doesn't wait for the images to load. */
export async function addImages(
    ids: string[],
    target: AddImagesTarget,
): Promise<void> {
    if (target.subTaskId !== null) await saveLinks(target.subTaskId, ids);
    void target.setInstanceIDs(ids);
    if (target.rewriteUrl) {
        // history.replaceState (view-state) is not mirrored into page.url.
        const params = new URLSearchParams(window.location.search);
        params.set("instances", ids.join(","));
        // eslint-disable-next-line svelte/no-navigation-without-resolve -- query-only navigation on the current route
        void goto(`?${params.toString()}`.replaceAll("%2C", ","));
    }
}

// One request at a time: each reply is the set's whole image list, so parallel replies would arrive out of order.
async function saveLinks(subTaskId: number, ids: string[]): Promise<void> {
    // Against the server's list, so a retry after a partial save resends nothing that succeeded.
    const saved = (subtasks.get(subTaskId)?.images ?? []).map((image) =>
        String(image.id),
    );
    try {
        for (const id of saved.filter((id) => !ids.includes(id)))
            await removeSubTaskImage(subTaskId, id);
        for (const id of ids.filter((id) => !saved.includes(id)))
            await addSubTaskImage(subTaskId, id);
    } catch (e) {
        // The server's own message may name images or patients, so it isn't shown.
        if (e instanceof ApiError && isOutOfDeclaration(e))
            throw new Error(
                `Image project ${e.detail.image_projects.join(", ")}; ` +
                    `task declares ${e.detail.declared_projects.join(", ")}. ${NOT_APPLIED}`,
                { cause: e },
            );
        throw new Error(`${NOT_APPLIED} Try again.`, { cause: e });
    }
}

/** The picker's starting search: every image of the patients already open. */
export function patientConditions(instanceIds: readonly string[]): Condition[] {
    const identifiers = new Set<string>();
    for (const id of instanceIds) {
        const identifier = instances.get(id)?.patient?.identifier;
        if (identifier) identifiers.add(identifier);
    }
    if (identifiers.size === 0) return [];
    return [
        {
            type: "default",
            variable: "Patient Identifier",
            operator: "IN",
            value: [...identifiers],
        } as Condition,
    ];
}
