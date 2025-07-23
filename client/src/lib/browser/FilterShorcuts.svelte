<script lang="ts">
    import { browser } from "$app/environment";
    import { page } from "$app/state";
    import { data } from "$lib/datamodel/model";
    import { onMount } from "svelte";
    import { getContext } from "svelte";
    import { BrowserContext } from "./browserContext.svelte";
    import { goto } from "$app/navigation";

    const { projects } = data;
    const projectNames = projects.map((project) => project.name);

    const params = browser ? page.url.searchParams : new URLSearchParams();

    const browserContext = getContext<BrowserContext>("browserContext");

    let patientIdentifier: string | null = $state(
        params.get("PatientIdentifier"),
    );
    let date: string | null = $state(params.get("StudyDate"));
    let projectName: string | null = $state(params.get("ProjectName"));

    async function submitFilter(key: string, value: string | null) {
        // Reset all state variables
        patientIdentifier = key === "PatientIdentifier" ? value : null;
        date = key === "StudyDate" ? value : null;
        projectName = key === "ProjectName" ? value : null;

        // Update URL params
        params.forEach((_, k) => params.delete(k));
        if (value) {
            params.set(key, value);
        }
        await goto(`?${params.toString()}`);
        browserContext.loadDataFromServer();
    }

    async function submitPatientIdentifier(e: Event) {
        e.preventDefault();
        await submitFilter("PatientIdentifier", patientIdentifier);
    }

    async function submitDate(e: Event) {
        e.preventDefault();
        await submitFilter("StudyDate", date);
    }

    async function submitProjectName(e: Event) {
        e.preventDefault();
        await submitFilter("ProjectName", projectName);
    }

    let patientIdentifierInput: HTMLInputElement = $state();
    onMount(() => patientIdentifierInput.focus());
</script>

<!-- svelte-ignore a11y_label_has_associated_control -->
<div>
    <form onsubmit={submitPatientIdentifier}>
        <label> PatientIdentifier: </label>
        <input
            type="text"
            bind:this={patientIdentifierInput}
            bind:value={patientIdentifier}
            placeholder="PatientIdentifier"
        />
        <button type="submit" disabled={!patientIdentifier}>Search</button>
    </form>

    <form onsubmit={submitDate}>
        <label> Study date: </label>
        <input type="date" bind:value={date} />
        <button type="submit" disabled={!date}>Search</button>
    </form>

    <form onsubmit={submitProjectName}>
        <label> Project Name: </label>
        <select bind:value={projectName}>
            <option></option>
            {#each $projectNames as value}
                <option {value}>{value}</option>
            {/each}
        </select>
        <button type="submit" disabled={!projectName}>Search</button>
    </form>
</div>

<style>
    div {
        display: grid;
        grid-template-columns: 0fr 16em 0fr;
    }
    label {
        display: flex;
        padding-right: 1em;
        align-items: center;
    }
    input, select {
        margin-right: 1em;
    }
    form {
        display: contents;
    }
    
</style>
