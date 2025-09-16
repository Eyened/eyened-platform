<script lang="ts">
    import { Button } from "$lib/components/ui/button";
    import {
        Command,
        CommandEmpty,
        CommandGroup,
        CommandInput,
        CommandItem,
        CommandList,
    } from "$lib/components/ui/command";
    import {
        Dialog,
        DialogContent,
        DialogHeader,
        DialogTitle
    } from "$lib/components/ui/dialog";
    import {
        Popover,
        PopoverContent,
        PopoverTrigger,
    } from "$lib/components/ui/popover";
    import {
        Tooltip,
        TooltipContent,
        TooltipTrigger,
    } from "$lib/components/ui/tooltip";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { timeAgo } from '$lib/utils';
    import { faSquareXmark } from "@fortawesome/free-solid-svg-icons";
    import { getContext } from 'svelte';
    import Fa from "svelte-fa";
    import TagEditForm from "./TagEditForm.svelte";
    
    let { tagType, itemTagLinks = [], maxTags = 3, tag: onTag = (id: number) => {}, untag: onUntag = (id: number) => {} }: { 
        tagType: 'Annotation' | 'ImageInstance' | 'Study';
        itemTagLinks?: any[];
        maxTags?: number;
        tag?: (id: number) => void;
        untag?: (id: number) => void;
    } = $props();
    
    const {tagsStore, creatorsStore} = getContext<GlobalContext>('globalContext');
    const {studyTags, imageInstanceTags, annotationTags, studyTagNames, imageInstanceTagNames, annotationTagNames} = tagsStore;
    
    let itemTagIDs = $derived(itemTagLinks.map(link => link.TagID));
    const tags = tagType === 'Annotation' ? annotationTags : tagType === 'ImageInstance' ? imageInstanceTags : studyTags;
    const tagNames = tagType === 'Annotation' ? annotationTagNames : tagType === 'ImageInstance' ? imageInstanceTagNames : studyTagNames;
    
    // Tags that can be added to the item
    let dropdownTags = $derived(() => {
        const itemTagsSet = new Set(itemTagIDs);
        return $tags.filter(tag => !itemTagsSet.has(tag.TagID));
    });
    // Tags the item has
    let itemTags = $derived(itemTagLinks.map(link => ({
        ...$tagsStore.byId[link.TagID],
        ...link
    })).sort((a, b) => +b.Created - +a.Created));
    
    let textValue: string;
    let value = $state("");
    let dropdownOpen = $state(false);
    let dialogOpen = $state(false);
    
    $effect(() => {
        console.log('value', value);
    });
    
    function linkTag(tagName: string) {
        const tagID = $tags.find((t) => t.TagName === tagName)?.TagID;
        if(tagID !== undefined) {
            onTag(tagID)
        }
    }
    function removeTag(tagID: number) {
        onUntag(tagID)
    }
    function handleCreateTag(payload) {
        tagsStore.createTag(payload);
        setDialogOpen(false)
    }
    function handleCommandKeydown(event) {
        if (event.key === 'Enter') {
            if($tagNames.has(value)) {
                linkTag(value)
                setValue('')
            } else {
                setDialogOpen(true)
            }
        }
    }
    function setValue(newValue: string) {
        value = newValue
    }
    function setDropdownOpen(newOpen: boolean) {
        dropdownOpen = newOpen
    }
    function setDialogOpen(newOpen: boolean) {
        dialogOpen = newOpen
    }
</script>
<div class="tagging-component">
    <!-- Dialog with the new tag form -->
    <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
            <DialogHeader>
            <DialogTitle>New Tag</DialogTitle>
                {value}
                <TagEditForm {tagType} initTagName={textValue} add={handleCreateTag} />
            </DialogHeader>
        </DialogContent>
    </Dialog>
    <!-- Combobox for adding new tags -->
    <!-- see: https://ui.shadcn.com/docs/components/combobox-->
    <Popover open={dropdownOpen} onOpenChange={setDropdownOpen}>
        <PopoverTrigger>
            <Button
                variant="outline"
                role="combobox"
                class="w-[200px] justify-between"
            >
                Add tag...
            </Button>
        </PopoverTrigger>
        <PopoverContent class="w-40">
            <Command value={value} onValueChange={setValue} onkeydown={handleCommandKeydown}>
                <CommandInput bind:value={textValue} placeholder="Search tags..." />
                <CommandList>
                    <CommandEmpty>No tags found.</CommandEmpty>
                    <CommandGroup>
                        {#each dropdownTags as tag}
                        <CommandItem
                            value={tag.TagName}
                            onSelect={() => {
                                linkTag(tag.TagName)
                                setValue(tag.TagName)
                                setDropdownOpen(false)
                            }}
                        >
                            {tag.TagName}
                        </CommandItem>
                        {/each}
                    </CommandGroup>
                </CommandList>
            </Command>
        </PopoverContent>
    </Popover>
    
    <!-- Display tags -->
    <div class="tags-list">
        {#each itemTags.slice(0, maxTags) as tag}
            <div class="tag">
                <Tooltip openDelay={50}>
                    <TooltipTrigger><span>{tag.TagName}</span></TooltipTrigger> 
                    <TooltipContent>
                        <p>{tag.TagDescription ? tag.TagDescription : 'No description'}</p>
                        <p>Tagged by {$creatorsStore.byId[tag.CreatorID].CreatorName} {timeAgo(tag.Created)}</p>
                    </TooltipContent>
                </Tooltip>
                <button class="ml-2 hover:text-red-700" onclick={() => removeTag(tag.TagID)} >
                    <Fa icon={faSquareXmark} size='lg'/>
                </button>
            </div>
        {/each}
        {#if itemTags.length > maxTags}
            <div class="tag plus-tag">
                <span>+{itemTags.length - maxTags}</span>
                <div class="overlay">
                    {#each itemTags.slice(maxTags) as tag}
                        <div class="tag overlay-tag">
                            <span>{tag.TagName} ({tag.TagCount})</span>
                        </div>
                    {/each}
                </div>
            </div>
        {/if}
    </div>
</div>
<style>
    /* .tagging-component {
        display: flex;
        flex-direction: column;
    } */
    .tags-list {
        display: inline-flex;
        /* display: flex; */
        flex-wrap: wrap;
        margin-top: 1em;
    }
    .tag {
        display: inline-flex;
        align-items: center;
        padding: 0.5em 1em;
        margin: 0.5em;
        border: 1px solid #ccc;
        border-radius: 20px;
        background-color: #f1f1f1;
        font-size: 0.9em;
    }
    .plus-tag {
        position: relative;
        cursor: pointer;
        background-color: #007bff;
        color: white;
        border-radius: 50%;
        padding: 0.5em;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    .overlay {
        position: absolute;
        top: 100%;
        left: 50%;
        transform: translateX(-50%);
        background: white;
        border: 1px solid #ccc;
        border-radius: 4px;
        padding: 0.5em;
        box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        display: none;
    }
    .plus-tag:hover .overlay {
        display: block;
    }
    .overlay-tag {
        margin: 0.2em 0;
    }
    .combobox {
        margin-top: 1em;
    }
</style>