<script lang="ts">
    import type { FormSchemaGET } from "../../../types/openapi_types";
    import { getContext } from "svelte";
    import type { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import RegistrationEyeGroup from "./RegistrationEyeGroup.svelte";
    import {
        groupKey,
        groupLabel,
        groupOpenImages,
        orderByInstanceIds,
        type OpenImage,
    } from "./groupOpenImages";

    interface Props {
        active: boolean;
        registrationSchema: FormSchemaGET;
    }
    const { active, registrationSchema }: Props = $props();
    // `active` stays in the panel contract. Read it in an effect so Svelte
    // does not treat the prop as captured once at init.
    $effect(() => {
        void active;
    });

    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );

    const openImages = $derived.by(() => {
        const images: OpenImage[] = [];
        for (const image of viewerWindowContext.topViewers.keys()) {
            // Skip only real volumes and slice stacks. Missing is2D stays.
            if (image.is2D === false) continue;
            images.push({
                imageId: image.image_id,
                instanceId: image.instance.id,
                patientId: image.instance.patient.id,
                patientIdentifier: image.instance.patient.identifier,
                laterality: image.instance.laterality ?? null,
                studyId: image.instance.study?.id,
            });
        }
        return orderByInstanceIds(
            images,
            viewerWindowContext.instanceIds ?? [],
        );
    });

    const groups = $derived(groupOpenImages(openImages));
    const boxed = $derived(groups.length > 1);
</script>

<div class="main">
    {#each groups as group (groupKey(group.patientId, group.laterality))}
        {#if boxed}
            {@const label = groupLabel(group)}
            <section class="group" aria-label={label}>
                <div class="group-label">{label}</div>
                <RegistrationEyeGroup {group} {registrationSchema} />
            </section>
        {:else}
            <RegistrationEyeGroup {group} {registrationSchema} />
        {/if}
    {/each}
</div>

<style>
    div.main {
        padding: 0.5em;
        min-height: 0;
        flex: 1 1 auto;
        overflow-y: auto;
    }
    section.group {
        margin: 0 0 0.75em;
    }
    .group-label {
        font-size: 0.75em;
        opacity: 0.8;
        margin-bottom: 0.35em;
    }
</style>
