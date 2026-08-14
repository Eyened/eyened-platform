<script lang="ts">
    import { goto } from "$app/navigation";
    import Browser from "$lib/browser/Browser.svelte";
    import {
        BrowserContext,
        type Condition,
    } from "$lib/browser/browserContext.svelte";
    import { Button } from "$lib/components/ui/button";
    import { addSubTaskImage, removeSubTaskImage } from "$lib/data/helpers";
    import { instances } from "$lib/data/stores.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import { getContext, onDestroy } from "svelte";
    import type { ImageGET } from "../../types/openapi_types";
    import { ViewerWindowContext } from "./viewerWindowContext.svelte";

    interface Props {
        viewerWindowContext: ViewerWindowContext;
        onClose?: () => void;
    }
    let { viewerWindowContext, onClose }: Props = $props();

    // The overlay owns the context so it can read the selection back out on close.
    const browserContext = new BrowserContext();
    browserContext.urlSync = false;
    browserContext.limit = 100;

    const initialInstanceIds = viewerWindowContext.instanceIds.slice();

    const taskContext = getContext<TaskContext>("taskContext");
    const subTask = taskContext?.subTask;

    // whether to update the image links in the database
    let updateImageLinks = $state(false);

    // Default query: all images for the patients in the current selection.
    const initialConditions: Condition[] = (() => {
        const patientIdentifiers = new Set<string>();
        for (const instanceId of initialInstanceIds) {
            const instance = instances.get(instanceId) as ImageGET | undefined;
            if (instance?.patient?.identifier) {
                patientIdentifiers.add(instance.patient.identifier);
            } else if (!instance) {
                console.error("Instance not found", instanceId);
            }
        }
        if (patientIdentifiers.size === 0) return [];
        return [
            {
                type: "default",
                variable: "Patient Identifier",
                operator: "IN",
                value: Array.from(patientIdentifiers),
            } as Condition,
        ];
    })();

    async function updateSubTaskImageLinks(currentInstanceIds: string[]) {
        const newInstanceIds = currentInstanceIds.filter(
            (id) => !initialInstanceIds.includes(id),
        );
        const removedInstanceIds = initialInstanceIds.filter(
            (id) => !currentInstanceIds.includes(id),
        );

        // Run sequentially: each endpoint returns a full snapshot of the
        // subtask's images, so parallel requests would ingest out-of-order
        // (stale) snapshots and also race on the next ImageIndex.
        for (const id of removedInstanceIds) {
            await removeSubTaskImage(subTask!.id, id);
        }
        for (const id of newInstanceIds) {
            await addSubTaskImage(subTask!.id, id);
        }
    }

    function close() {
        const currentInstanceIds = [...browserContext.selectedIds];
        if (subTask) {
            if (updateImageLinks) {
                updateSubTaskImageLinks(currentInstanceIds);
            }
        }
        // Prune/persist before goto so the snapshot includes the updated v=.
        viewerWindowContext.setInstanceIDs(currentInstanceIds);
        if (!subTask) {
            // history.replaceState (view-state) is not mirrored into page.url.
            // eslint-disable-next-line svelte/prefer-svelte-reactivity -- one-shot close() rewrite
            const searchParams = new URLSearchParams(window.location.search);
            searchParams.set("instances", currentInstanceIds.join(","));
            // eslint-disable-next-line svelte/no-navigation-without-resolve -- query-only nav on current route
            goto(`?${searchParams.toString()}`.replaceAll("%2C", ","));
        }
    }
    onDestroy(close);
</script>

<div id="browser-overlay" class="browser-light-surface">
    <div class="header">
        <span class="title">Browse images</span>
        {#if subTask}
            <label class="task-option" for="updateImageLinks">
                Update task image links
                <input
                    id="updateImageLinks"
                    type="checkbox"
                    bind:checked={updateImageLinks}
                />
            </label>
        {/if}
        <div class="actions">
            <Button variant="outline" size="sm" onclick={() => onClose?.()}>
                Close
            </Button>
        </div>
    </div>
    <div class="body">
        <Browser
            context={browserContext}
            mode="overlay"
            syncUrl={false}
            {initialConditions}
            initialSelectedIds={initialInstanceIds}
        />
    </div>
</div>

<style>
    div#browser-overlay {
        /* Render as a centered popup card rather than filling the panel */
        display: flex;
        flex-direction: column;
        width: min(95vw, 100%);
        height: min(95vh, 100%);
        margin: auto;
        background-color: var(--background);
        border-radius: 12px;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
        overflow: hidden;
    }
    div#browser-overlay .header {
        flex: 0 0 auto;
        display: flex;
        align-items: center;
        gap: 1em;
        padding: 0.5em 1em;
        border-bottom: 1px solid var(--border);
    }
    div#browser-overlay .header .title {
        font-weight: bold;
    }
    div#browser-overlay .header .task-option {
        display: flex;
        align-items: center;
        gap: 0.5em;
        margin-left: auto;
        font-size: 0.875rem;
        cursor: pointer;
    }
    div#browser-overlay .header .actions {
        flex: 0 0 auto;
        margin-left: auto;
    }
    div#browser-overlay .header .task-option + .actions {
        margin-left: 0;
    }
    div#browser-overlay .body {
        flex: 1 1 auto;
        min-height: 0;
        display: flex;
        flex-direction: column;
        overflow-y: auto;
    }
</style>
