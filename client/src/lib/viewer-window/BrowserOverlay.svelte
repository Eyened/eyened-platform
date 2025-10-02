<script lang="ts">
    import { goto } from "$app/navigation";
    import { page } from "$app/state";
    import BrowserContent from "$lib/browser/BrowserContent.svelte";
    import { BrowserContext } from "$lib/browser/browserContext.svelte";
    import InstanceComponent from "$lib/browser/InstanceComponent.svelte";
    import { SubTasksRepo } from "$lib/data/repos.svelte";
    import type { TaskContext } from "$lib/types";
    import { getContext, setContext } from "svelte";
    import { ViewerWindowContext } from "./viewerWindowContext.svelte";

    interface Props {
        viewerWindowContext: ViewerWindowContext;
    }

    let { viewerWindowContext }: Props = $props();
    const instanceIds = viewerWindowContext.instanceIds;
    const initialInstanceIds = $instanceIds.slice();

    const browserContext = new BrowserContext(initialInstanceIds);

    setContext("browserContext", browserContext);

    const taskContext = getContext<TaskContext>("taskContext");
    const subTask = taskContext?.subTask;

    // whether to update the image links in the database
    let updateImageLinks = $state(false);

    function close() {
        viewerWindowContext.closeBrowserOverlay();

        const currentInstanceIds = [...browserContext.selectedIds];
        if (subTask) {
            if (updateImageLinks) {
                updateSubTaskImageLinks(currentInstanceIds);
            }
        } else {
            // updates url (just visual, does not reload the page)
            const searchParams = page.url.searchParams;
            searchParams.set("instances", currentInstanceIds.join(","));
            goto(`?${page.url.searchParams.toString()}`.replaceAll("%2C", ","));
        }
        viewerWindowContext.setInstanceIDs(currentInstanceIds);
    }

    async function updateSubTaskImageLinks(currentInstanceIds: number[]) {
        const newInstanceIds = currentInstanceIds.filter(
            (id) => !initialInstanceIds.includes(id),
        );
        const removedInstanceIds = initialInstanceIds.filter(
            (id) => !currentInstanceIds.includes(id),
        );

        const SubTasks = new SubTasksRepo('browser-overlay');
        const subTaskObj = SubTasks.object(subTask!.id);
        for (const instanceId of newInstanceIds) {
            await subTaskObj.addImage(instanceId);
        }
        for (const instanceId of removedInstanceIds) {
            await subTaskObj.removeImage(instanceId);
        }
    }
</script>

<div id="browser-overlay">
    <div class="button-container">
        {#if subTask}
            <label for="updateImageLinks">Update task image links</label>
            <input
                id="updateImageLinks"
                type="checkbox"
                bind:checked={updateImageLinks}
            />
        {/if}
        <button class="close-button" onclick={close}>Close</button>
    </div>
    <div id="selection">
        {#each browserContext.selectedInstances as instance (instance.id)}
            <InstanceComponent {instance} />
        {/each}
    </div>
    <div id="content">
        <BrowserContent mode="overlay" />
    </div>
</div>

<style>
    div#browser-overlay {
        position: fixed;
        z-index: 100;
        left: 0;
        top: 0;
        bottom: 0;
        right: 0;
        background-color: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(10px); /* Add this line */

        transition: 0.5s;
        display: flex;
        flex-direction: column;
    }
    div#content {
        flex: 1;
        display: flex;
        flex-direction: column;
        padding: 1em;
        overflow-y: auto;
    }
    div#selection {
        display: flex;
        background-color: black;
    }
    .button-container {
        display: flex;
        justify-content: center;
        padding: 20px;
    }
    label {
        align-self: center;
    }
    .close-button {
        background-color: #85c1e9;
        color: #333;
        font-size: 18px;
        padding: 10px 24px;
        border: none;
        cursor: pointer;
        border-radius: 5px;
        transition: 0.3s;
    }
    .close-button:hover {
        background-color: #6cb6e7; /* Darker blue on hover */
    }
</style>
