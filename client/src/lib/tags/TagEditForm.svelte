<script lang="ts">
    // icons from: https://fontawesome.com/v6/icons?o=r&m=free&s=solid
    import { createEventDispatcher } from 'svelte'
    import type { Tag } from '../datamodel/tag'
    export let tagType: 'Annotation' | 'ImageInstance' | 'Study'
    export let initTagName = '';
    export let initTagDescription = '';
    let newTagName = initTagName;
    let newTagDescription = initTagDescription;
    console.log('TagEditForm', tagType, initTagName, initTagDescription);
    const dispatch = createEventDispatcher<{add: Partial<Tag>}>();
    function addTag() {
        if (newTagName.trim() !== '') {
            dispatch('add', { name: newTagName, description: newTagDescription, type: tagType });
            newTagName = '';
            newTagDescription = '';
        }
    }
</script>
<div class="new-tag-input">
    <input
        type="text"
        placeholder="New tag name"
        maxlength="256"
        bind:value={newTagName}/>
    <input
        type="text"
        placeholder="Short tag description"
        maxlength="256"
        bind:value={newTagDescription}
        on:keydown={(e) => e.key === 'Enter' && addTag()} />
    <button on:click={addTag}>Add</button>
</div>
<style>
    .new-tag-input {
        margin-top: 1em;
        display: flex;
    }
    .new-tag-input input {
        flex-grow: 1;
        padding: 0.5em;
        font-size: 1em;
        border: 1px solid #ccc;
        border-radius: 4px;
        margin-right: 0.5em;
    }
    .new-tag-input button {
        padding: 0.5em 1em;
        font-size: 1em;
        border: none;
        background-color: #007bff;
        color: white;
        border-radius: 4px;
        cursor: pointer;
    }
    .new-tag-input button:hover {
        background-color: #0056b3;
    }
</style>