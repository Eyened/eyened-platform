<script lang="ts">
    import { AnnotationType } from "$lib/datamodel/annotationType.svelte";
    import { data } from "$lib/datamodel/model";
    import AnnotationTypeRow from "./AnnotationTypeRow.svelte";

    const { annotationTypes } = data;

    let name = $state("");
    let dataRepresentation = $state("MULTI_LABEL");
    function createAnnotationType(event: Event) {
        event.preventDefault();
        AnnotationType.create({ name, dataRepresentation });
        name = "";
    }
</script>

<div class="main">
    <h1>Annotation Types</h1>
    <div class="new-annotation-type">
        <span>New Annotation Type:</span>
        <form onsubmit={createAnnotationType}>
            <input type="text" bind:value={name} />
            <select bind:value={dataRepresentation}>
                <option value="MULTI_LABEL">Multi Label</option>
                <option value="MULTI_CLASS">Multi Class</option>
            </select>
            <button type="submit">Create</button>
        </form>
    </div>
    <ul class="feature-list">
        {#each $annotationTypes as annotationType}
            <AnnotationTypeRow {annotationType} />
        {/each}
    </ul>
</div>

<style>
    div {
        display: flex;
    }
    .main {
        flex-direction: column;
        padding: 1em;
    }
    .new-annotation-type {
        flex-direction: row;
    }

    div.main {
        overflow-y: auto;
    }
</style>
