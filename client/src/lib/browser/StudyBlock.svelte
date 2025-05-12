<script lang="ts">
    import Eye from "./Eye.svelte";
    import Icon from "$lib/gui/Icon.svelte";
    import type { Study } from "$lib/datamodel/study";
    import StudyBlockForms from "./StudyBlockForms.svelte";
    import AdditionalDataSources from "./AdditionalDataSources.svelte";
    import extensions from "$lib/extensions";
    
    interface Props {
        study: Study;
        mode?: "full" | "overlay";
    }

    let { study, mode = "full" }: Props = $props();

    let collapse = $state(false);

    const age = Math.floor(
        (study.date - study.patient.birthDate) / (1000 * 60 * 60 * 24 * 365.25),
    );

    const context = {
        study,
        patient: study.patient,
        project: study.patient.project,
    };
    const { additional_data_sources } = extensions.browser.study;

</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="main block">
    <div class="header" onclick={() => (collapse = !collapse)}>
        {#if !collapse}
            ▼
        {:else}
            ►
        {/if}
        <div class="date-age">
            <div class="date">
                <Icon icon="calendar" />
                {study.date.toISOString().slice(0, 10)}
            </div>
            <div class="age">({age} years)</div>
        </div>
    </div>
    <div class:collapse class="eyes">
        <div>
            <Eye laterality="R" {study} />
            <Eye laterality="L" {study} />
        </div>

        {#if mode == "full"}
            <StudyBlockForms {study} />
            <AdditionalDataSources {context} {additional_data_sources} />
        {/if}
    </div>
</div>

<style>
    div.block {
        padding: 0.3em;
        flex-direction: column;
        
        border: 1px solid rgb(181, 188, 206);
        border-radius: 2px;
        box-shadow: rgba(149, 157, 165, 0.2) 0px 6px 12px;
        margin-bottom: 1em;

    }
    div {
        display: flex;
    }
    div.header {
        font-size: large;
        font-weight: bold;
        cursor: pointer;
        align-items: center;
    }
    div.header > div {
        margin: 0.1em;
        align-items: center;
    }
    div.header:hover {
        background-color: lightgray;
    }
    div.collapse {
        display: none;
    }
    div.eyes {
        flex-direction: column;
    }
    div.date {
        font-size: normal;
    }
    div.date-age {
        align-items: center;
    }
    div.date-age > div {
        margin: 0.1em;
    }
</style>
