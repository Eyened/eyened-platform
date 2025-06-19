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
    {#each $sorted_studies as study (study)}
        <StudyBlock {study} {mode} />
    {/each}
    {#if mode == "full"}
        <AdditionalDataSources {context} {additional_data_sources} />
    {/if}
</div>

<style>
    div {
        display: flex;
    }
    .patient-info {
        font-size: large;
        flex-direction: column;

        box-shadow: rgba(149, 157, 165, 0.2) 0px 6px 12px;
        margin-bottom: 1em;
        padding-bottom: 1em;
    }
    .header {
        border-top: 1px solid rgb(181, 188, 206);
        border-left: 1px solid rgb(181, 188, 206);
        border-right: 1px solid rgb(181, 188, 206);
        
        border-top-left-radius: 2px;
        border-top-right-radius: 2px;
        padding: 0.3em;
        background-color: var(--browser-background);
    }
</style>
