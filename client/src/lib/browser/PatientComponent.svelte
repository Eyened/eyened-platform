<script lang="ts">
    import type { Patient } from "$lib/datamodel/patient";
    import { derived } from "svelte/store";
    import AdditionalDataSources from "./AdditionalDataSources.svelte";
    import StudyBlock from "./StudyBlock.svelte";
    import Icon from "$lib/gui/Icon.svelte";
    import extensions from "$lib/extensions";

    interface Props {
        patient: Patient;
        mode?: "full" | "overlay";
    }
    let { patient, mode = "full" }: Props = $props();
    const studies = patient.studies;
    const sorted_studies = derived(studies, (studies) => {
        return [...studies].sort((a, b) => b.date - a.date);
    });

    const context = {
        patient,
        project: patient.project,
    };
    const { additional_data_sources } = extensions.browser.patient;
</script>

<div class="patient-info">
    <div class="header">
        <Icon icon="patient" />
        <div>{patient.identifier}</div>
        {#if patient.sex}
            <div class="sex-age">
                [{patient.sex}]
            </div>
        {/if}
    </div>
    <div class="content">
        {#each $sorted_studies as study (study)}
            <StudyBlock {study} {mode} />
        {/each}
        {#if mode == "full"}
            <AdditionalDataSources {context} {additional_data_sources} />
        {/if}
    </div>
</div>

<style>
    div {
        display: flex;
    }
    .patient-info {
        font-size: large;
        flex-direction: column;
        margin: 0.5em;
        border: 1px solid rgb(181, 188, 206);
        border-top-left-radius: 2px;
        border-top-right-radius: 2px;
    }
    .header {
        padding: 0.3em;
        background-color: var(--browser-background);
    }
    div.content {
        flex-direction: column;
        margin: 0.5em;
    }
</style>
