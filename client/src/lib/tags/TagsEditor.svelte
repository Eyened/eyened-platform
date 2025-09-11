<script lang="ts">
    import Fa from 'svelte-fa'
// icons from: https://fontawesome.com/v6/icons?o=r&m=free&s=solid
    import {
        AlertDialog,
        AlertDialogCancel,
        AlertDialogContent,
        AlertDialogDescription,
        AlertDialogFooter,
        AlertDialogHeader,
        AlertDialogTitle
    } from "$lib/components/ui/alert-dialog"
    import {
        Tooltip,
        TooltipContent,
        TooltipTrigger,
    } from "$lib/components/ui/tooltip"
    import { data } from '$lib/datamodel/model'
    import { faStar, faTrash } from '@fortawesome/free-solid-svg-icons'
    import { getContext } from 'svelte'
    import { Button } from '../components/ui/button'
    import { GlobalContext } from '../data-loading/globalContext'
    import { CreatorTagConstructor, type Tag } from '../datamodel/tag'
    import TagEditForm from './TagEditForm.svelte'


    export let tagType: 'Annotation' | 'ImageInstance' | 'Study' = 'Annotation';


    const { tags: tagsCollection, creatorTags: creatorTagsCollection } = data;
    const {creator} = getContext<GlobalContext>('globalContext');
    $: dialogOpen = tagToDelete !== null;

    const tags = tagsCollection.filter(tag => tag.type == tagType)
    // $: tags = $allTags.filter(tag => tag.TagType === tagType);
    let favouriteTagIDs: Set<number>;
    $: favouriteTagIDs = new Set($creatorTagsCollection.map(ct => ct.tag.id))

    let tagToDelete : number | null = null;
    const setDialogOpen = (value: boolean) => {
        if (!value) {
            tagToDelete = null;
        }
    }
    function handleClickDelete(tagID: number) {
        tagToDelete = tagID;
    }

    function handleClickStar(tagID: number) {
        if (favouriteTagIDs.has(tagID)) {
            creatorTagsCollection.delete(
                {id: CreatorTagConstructor.getID({CreatorID: creator.id, TagID: tagID})}
            )
        } else {
            creatorTagsCollection.create({
                creator: creator,
                tag: tagsCollection.get(tagID)
            })
        }
    }

    function handleCreateTag(event: CustomEvent<Partial<Tag>>) {
        tagsCollection.create(event.detail)
        // tagsStore.createTag(detail);
    }
    function handleDeleteTag() {
        if (tagToDelete === null) {
            return;
        }
        tagsCollection.delete({id: tagToDelete});
        tagToDelete = null;
    }
</script>
<div>
    <AlertDialog open={dialogOpen} onOpenChange={setDialogOpen}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
          <AlertDialogDescription>
            This action cannot be undone. This will permanently delete the tag.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <Button on:click={handleDeleteTag}>Yes, Delete</Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>

    <div class="border-radius-5 bg-gray-100 p-4">
        <TagEditForm {tagType} on:add={handleCreateTag}/>
    </div>
    {#each $tags.sort((a, b) => a.name.localeCompare(b.name)) as tag}
        <div class:!bg-orange-200={favouriteTagIDs.has(tag.id)} class="relative inline-flex items-center py-2 px-2 m-1 border-1 border-gray-500 rounded-lg bg-gray-200 " >
            <button class="inline-block" on:click={() => handleClickStar(tag.id)}>
                <Fa icon={faStar} class="inline-block"/>
            
                <Tooltip openDelay={50}>
                    <TooltipTrigger><span>{tag.name} ({tag.name}) </span></TooltipTrigger> 
                    <TooltipContent>
                        <p>{tag.description ? tag.description : 'No description'}</p>
                    </TooltipContent>
                </Tooltip>
            </button>
            <button class="delete" on:click={() => handleClickDelete(tag.id)}>
                <Fa icon={faTrash}/>
            </button>
            
        </div>
    {/each}
    
</div>
<style>
    /* .tag {
        display: inline-flex;
        align-items: center;
        padding: 0.5em 1em;
        margin: 0.5em;
        border: 1px solid #ccc;
        border-radius: 20px;
        background-color: #f1f1f1;
        font-size: 0.9em;
        position: relative;
    } */
    /* .tag span {
        margin-right: 0.5em;
    } */
    .delete {
        background: red;
        color: white;
        border: none;
        border-radius: 50%;
        width: 20px;
        height: 20px;
        display: flex;
        justify-content: center;
        align-items: center;
        cursor: pointer;
        margin-left: 0.5em;
    }
</style>