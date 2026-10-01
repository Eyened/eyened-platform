<script lang="ts">
    import AdditionalDataSources from "$lib/browser/AdditionalDataSources.svelte";
    import extensions from "$lib/extensions";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import type { StudyGET } from "../../../types/openapi_types";
    import { loadPatientStudies, PATIENT_STUDY_LIMIT } from "./patientStudies";

    let { active = false }: { active?: boolean } = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const instance = viewerContext.image.instance;
    const patientIdentifier = instance.patient?.identifier ?? undefined;
    const currentStudyId = instance.study?.id;

    const { additional_data_sources } = extensions.viewer.panel_info;

    let studies = $state<StudyGET[]>([]);
    let truncated = $state(false);
    let loading = $state(false);
    let failed = $state(false);
    let openIds = $state<number[]>([]);
    let seededOpen = false;

    $effect(() => {
        if (!active || !patientIdentifier) return;
        let cancelled = false;
        loading = true;
        failed = false;
        loadPatientStudies(patientIdentifier)
            .then((result) => {
                if (cancelled) return;
                studies = result.studies;
                truncated = result.truncated;
                if (!seededOpen) {
                    seededOpen = true;
                    if (
                        currentStudyId != null &&
                        result.studies.some(
                            (study) => study.id === currentStudyId,
                        )
                    ) {
                        openIds = [currentStudyId];
                    }
                }
            })
            .catch(() => {
                if (!cancelled) failed = true;
            })
            .finally(() => {
                if (!cancelled) loading = false;
            });
        return () => {
            cancelled = true;
        };
    });

    function toggle(id: number) {
        openIds = openIds.includes(id)
            ? openIds.filter((openId) => openId !== id)
            : [...openIds, id];
    }

    function visitDate(study: StudyGET) {
        return study.date.split("T")[0];
    }
</script>

<div class="visits">
    {#if !patientIdentifier}
        <p>This image has no patient identifier.</p>
    {:else if loading && studies.length === 0}
        <p>Loading visits…</p>
    {:else if failed && studies.length === 0}
        <p>Could not load visits.</p>
    {:else if active && !loading && studies.length === 0}
        <p>No visits found for this patient.</p>
    {:else}
        <ul>
            {#each studies as study (study.id)}
                {@const open = openIds.includes(study.id)}
                <li>
                    <button
                        type="button"
                        aria-expanded={open}
                        onclick={() => toggle(study.id)}
                    >
                        {#if open}▼{:else}►{/if}
                        {visitDate(study)}
                        <span class="project">{study.project.name}</span>
                        {#if study.id === currentStudyId}
                            <span class="current">this visit</span>
                        {/if}
                    </button>
                    {#if open}
                        <div class="sources">
                            <AdditionalDataSources
                                context={{
                                    study,
                                    patient: study.patient,
                                    project: study.project,
                                }}
                                {additional_data_sources}
                            />
                        </div>
                    {/if}
                </li>
            {/each}
        </ul>
        {#if truncated}
            <p class="note">
                Showing the {PATIENT_STUDY_LIMIT} most recent visits.
            </p>
        {/if}
    {/if}
</div>

<style>
    .visits {
        display: flex;
        flex-direction: column;
        gap: 0.4em;
        min-width: 18em;
        padding: 0.5em;
    }
    ul {
        display: flex;
        flex-direction: column;
        gap: 0.35em;
        margin: 0;
        padding: 0;
        list-style: none;
    }
    button {
        color: inherit;
        background: transparent;
        border: none;
        padding: 0.15em 0;
        text-align: left;
        cursor: pointer;
    }
    .project {
        opacity: 0.75;
    }
    .current {
        margin-left: 0.4em;
        font-size: 0.75em;
        opacity: 0.8;
    }
    .sources {
        margin: 0.2em 0 0.4em;
    }
    .note {
        margin: 0;
        font-size: 0.8em;
        opacity: 0.75;
    }
</style>
