<script lang="ts">
	import type { TagType } from "../../types/openapi_types";

    // icons from: https://fontawesome.com/v6/icons?o=r&m=free&s=solid
    let { tagType, initTagName = '', initTagDescription = '', add }: { 
        tagType: TagType;
        initTagName?: string;
        initTagDescription?: string;
        add: (payload: { name: string; description: string; tagType: TagType }) => void;
    } = $props();
    
    let newTagName = $state(initTagName);
    let newTagDescription = $state(initTagDescription);
    console.log('TagEditForm', tagType, initTagName, initTagDescription);
    
    function addTag() {
        if (newTagName.trim() !== '') {
            add({ name: newTagName, description: newTagDescription, tagType: tagType });
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
        onkeydown={(e) => e.key === 'Enter' && addTag()} />
    <button onclick={addTag}>Add</button>
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