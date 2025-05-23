<script lang="ts">
    import InstanceComponent from "$lib/browser/InstanceComponent.svelte";
    import { getContext, setContext } from "svelte";
    import { ViewerWindowContext } from "./viewerWindowContext.svelte";
    import { data } from "$lib/datamodel/model";
    import { goto } from "$app/navigation";
    import { page } from "$app/state";
    import { BrowserContext } from "$lib/browser/browserContext.svelte";
    import BrowserContent from "$lib/browser/BrowserContent.svelte";
    import { loadParams } from "$lib/datamodel/api";
    import type { TaskContext } from "$lib/types";

    interface Props {
        viewerWindowContext: ViewerWindowContext;
    }

    let { viewerWindowContext }: Props = $props();
    const { subTaskImageLinks, instances } = data;
    const instanceIds = viewerWindowContext.instanceIds;
    const initialInstanceIds = $instanceIds;

    const browserContext = new BrowserContext(initialInstanceIds);

    setContext("browserContext", browserContext);

    const patientIds = initialInstanceIds.map(
        (i) => instances.get(i)!.patient.identifier,
    );
    const loading = loadParams({ PatientIdentifier: patientIds });

    const taskContext = getContext<TaskContext>("taskContext");
    const subTask = taskContext?.subTask;

    // whether to update the image links in the database
    let updateImageLinks = $state(false);

    function close() {
        viewerWindowContext.closeBrowserOverlay();

        const currentInstanceIds = [...browserContext.selection];
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

    function updateSubTaskImageLinks(currentInstanceIds: number[]) {
        const newInstanceIds = currentInstanceIds.filter(
            (id) => !initialInstanceIds.includes(id),
        );
        const removedInstanceIds = initialInstanceIds.filter(
            (id) => !currentInstanceIds.includes(id),
        );

        for (const instanceid of newInstanceIds) {
            subTaskImageLinks.create({ subTask, instanceid });
        }
        for (const instanceid of removedInstanceIds) {
            const link = subTaskImageLinks.find(
                (link) =>
                    link.subTask == subTask && link.instanceid == instanceid,
            );
            if (link) {
                subTaskImageLinks.delete(link);
            } else {
                console.error("Could not find link to delete");
            }
        }
    }
</script>

<div id="browser-overlay">
    <div class="button-container">
        {#if subTask}
            <label for="updateImageLinks">Update image links</label>
            <input
                id="updateImageLinks"
                type="checkbox"
                bind:checked={updateImageLinks}
            />
        {/if}
        <button class="close-button" onclick={close}>Close</button>
    </div>
    <div id="selection">
        {#each browserContext.selection.map((i) => instances.get(i)!) as instance (instance.id)}
            <InstanceComponent {instance} />
        {/each}
    </div>
    <div id="content">
        {#await loading}
            <div class="loader">Loading...</div>
        {:then}
            <BrowserContent mode="overlay" />
        {/await}
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
