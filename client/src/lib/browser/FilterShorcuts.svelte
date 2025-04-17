<script lang="ts">
    import { browser } from "$app/environment";
    import { page } from "$app/state";
    import { data } from "$lib/datamodel/model";
    import { onMount } from "svelte";

    const { projects } = data;
    const projectNames = projects.map((project) => project.name);

    const params = browser ? page.url.searchParams : new URLSearchParams();

    function search(key: string, value: string | null) {
        if (!value) return;
        const searchParams = new URLSearchParams();
        searchParams.set(key, value);

        const url = new URL(page.url);
        url.search = searchParams.toString();
        location.href = url.toString();
    }

    let patientIdentifier: string | null = $state(
        params.get("PatientIdentifier"),
    );
    let date: string | null = $state(params.get("StudyDate"));
    let projectName: string | null = $state(params.get("ProjectName"));

    function submitPatientIdentifier(e: Event) {
        e.preventDefault();
        search("PatientIdentifier", patientIdentifier);
    }

    function submitDate(e: Event) {
        e.preventDefault();
        search("StudyDate", date);
    }

    function submitProjectName(e: Event) {
        e.preventDefault();
        search("ProjectName", projectName);
    }

    let patientIdentifierInput: HTMLInputElement = $state();
    onMount(() => patientIdentifierInput.focus());
</script>

<!-- svelte-ignore a11y_label_has_associated_control -->
<div>
    <form onsubmit={submitPatientIdentifier}>
        <label> PatientIdentifier </label>
        <input
            type="text"
            bind:this={patientIdentifierInput}
            bind:value={patientIdentifier}
            placeholder="PatientIdentifier"
        />
        <button type="submit" disabled={!patientIdentifier}>Search</button>
    </form>

    <form onsubmit={submitDate}>
        <label> Study date: </label> <input type="date" bind:value={date} />
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
        display: flex;
        flex-direction: column;
    }
    form {
        display: grid;
        gap: 1em;
        grid-template-columns: 10em 12em 10em;
    }
</style>
