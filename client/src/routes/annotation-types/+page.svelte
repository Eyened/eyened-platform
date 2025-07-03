<script lang="ts">
    import { AnnotationType } from "$lib/datamodel/annotationType.svelte";
    import { data } from "$lib/datamodel/model";
    import AnnotationTypeRow from "./AnnotationTypeRow.svelte";

    const { annotationTypes } = data;

    let name = $state("");
    let dataRepresentation = $state("MultiLabel");
    let dataTypeInt = $state('8');

    function createAnnotationType(event: Event) {
        const dataType = {
            '8': 'R8UI',
            '16': 'R16UI',
            '32': 'R32UI',
        }[dataTypeInt];
        AnnotationType.create({ name, dataRepresentation, dataType});
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
                <option value="MultiLabel">Multi Label</option>
                <option value="MultiClass">Multi Class</option>
            </select>
            N Features:
            <label>
                <input
                    type="radio"
                    name="dataType"
                    value="8"
                    bind:group={dataTypeInt}
                />
                {"< 8"}
            </label>
            <label>
                <input
                    type="radio"
                    name="dataType"
                    value="16"
                    bind:group={dataTypeInt}
                />
                {"< 16"}
            </label>
            <label>
                <input
                    type="radio"
                    name="dataType"
                    value="32"
                    bind:group={dataTypeInt}
                />
                {"< 32"}
            </label>
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
