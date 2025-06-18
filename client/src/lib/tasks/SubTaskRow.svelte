<script lang="ts">
    import { page } from "$app/state";
    import { BrowserContext } from "$lib/browser/browserContext.svelte";
    import InstanceComponent from "$lib/browser/InstanceComponent.svelte";
    import { data } from "$lib/datamodel/model";

    import {
        SubTaskImageLink,
        type SubTask,
    } from "$lib/datamodel/subTask.svelte";
    import { setContext } from "svelte";

    interface Props {
        i: number;
        subTask: SubTask;
    }

    let { i, subTask }: Props = $props();
    const { state: taskState, instances } = subTask;

    const browserContext = new BrowserContext([]);
    browserContext.thumbnailSize = 4;
    setContext("browserContext", browserContext);

    let comments = $state(subTask.comments ?? "");

    function updateComments() {
        subTask.update({ comments });
    }

    async function handleGrade(index: number) {
        const suffix_string = `?${page.url.searchParams.toString()}`;
        const url = new URL(
            `${window.location.origin}/tasks/${subTask.task.id}/grade/${index}${suffix_string}`,
        );
        window.location.href = url.href;
    }
    let newImageId: number | undefined = $state();
    function addImage() {
        SubTaskImageLink.create({
            subTaskId: subTask.id,
            imageId: newImageId,
        });
    }

    function removeSelectedImages() {
        const imageIds = browserContext.selection.slice();
        for (const id of imageIds) {
            const link = data.subTaskImageLinks.get(`${subTask.id}_${id}`);
            if (link) {
                link.delete();
            } else {
                console.warn(`Link ${subTask.id}_${id} not found`);
            }
            browserContext.selection.splice(
                browserContext.selection.indexOf(id),
                1,
            );
        }
    }

    console.log(subTask.instances.map((instance) => instance.id));
    let imagesString = $state(
        subTask.instances.map((instance) => instance.id).$.join(","),
    );
</script>

<tr>
    <td>{i}</td>
    <td
        class:unknown={taskState.name == "Unknown"}
        class:ready={taskState.name == "Ready"}
        class:busy={taskState.name == "Busy"}
    >
        {taskState.name}
    </td>
    <td>
        <button onclick={() => handleGrade(i)}>View</button>
    </td>
    <td>
        <div class="instances">
            {#each $instances as instance}
                <InstanceComponent {instance} />
            {/each}
        </div>

        <input type="number" bind:value={newImageId} />
        <button onclick={addImage} disabled={newImageId == undefined}>
            Add image
        </button>

        <button
            onclick={removeSelectedImages}
            disabled={browserContext.selection.length == 0}
        >
            Remove {browserContext.selection.length} images from sub-task
        </button>
    </td>
    <td>
        <textarea bind:value={comments} onchange={updateComments} rows={3}>
        </textarea>
    </td>
</tr>

<style>
    div.instances {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4em;
    }
    td {
        padding-left: 0.8em;
        padding-right: 0.8em;
        padding-top: 0.4em;
        padding-bottom: 0.4em;
        border: 1px solid rgba(0, 0, 0, 0.1);
    }

    tr:nth-child(even) {
        background-color: #f8f8f8;
    }

    tr:nth-child(odd) {
        background-color: #fdfdfd;
    }

    tr:hover {
        background-color: #e0e0e0;
    }

    td.ready {
        background-color: greenyellow;
    }

    td.busy {
        background-color: orange;
    }

    td.unknown {
        background-color: lightgray;
    }
</style>
