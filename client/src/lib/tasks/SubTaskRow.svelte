<script lang="ts">
    import { page } from "$app/state";
    import { BrowserContext } from "$lib/browser/browserContext.svelte";
    import InstanceComponent from "$lib/browser/InstanceComponent.svelte";

    import type { SubTask } from "$lib/datamodel/subTask.svelte";
    import { setContext } from "svelte";

    interface Props {
        i: number;
        subTask: SubTask;
    }

    let { i, subTask }: Props = $props();
    const { state, instances } = subTask;

    async function handleGrade(index: number) {
        const suffix_string = `?${page.url.searchParams.toString()}`;
        const url = new URL(
            `${window.location.origin}/tasks/${subTask.task.id}/grade/${index}${suffix_string}`,
        );
        window.location.href = url.href;
    }
    const browserContext = new BrowserContext([]);
    browserContext.thumbnailSize = 4;
    setContext("browserContext", browserContext);
</script>

<tr>
    <td>{i}</td>
    <td
        class:unknown={state.name == "Unknown"}
        class:ready={state.name == "Ready"}
        class:busy={state.name == "Busy"}
    >
        {state.name}
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
