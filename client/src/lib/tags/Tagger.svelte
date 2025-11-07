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
		DialogTitle,
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
	import { createTag } from "$lib/data/helpers";
	import { tags } from "$lib/data/stores.svelte";
	import { timeAgo } from "$lib/utils";
	import { faSquareXmark } from "@fortawesome/free-solid-svg-icons";
	import Fa from "svelte-fa";
	import type { TagMeta, TagType } from "../../types/openapi_types";
	import TagEditForm from "./TagEditForm.svelte";

	let {
		tagType,
		tags: itemTags = [],
		maxTags = 3,
		tag: onTag = (id: number, comment?: string) => {},
		untag: onUntag = (id: number) => {},
		onUpdate = (id: number, comment?: string) => {},
	}: {
		tagType: TagType
		tags?: TagMeta[];
		maxTags?: number;
		tag?: (id: number, comment?: string) => void;
		untag?: (id: number) => void;
		onUpdate?: (id: number, comment?: string) => void;
	} = $props();
	
	const allTags = $derived(
		tags.filter(t => t.tag_type === (tagType === "Annotation" ? "FormAnnotation" : tagType))
	);

	// Build dropdown candidates (ids already in itemTags are excluded)
	const selectedIds = $derived(new Set(itemTags.map((t) => t.id)));
	const dropdownTags = $derived(allTags.filter((t) => !selectedIds.has(t.id)));
	
	let textValue = $state("");
	let value = $state("");
	let dropdownOpen = $state(false);
	let dialogOpen = $state(false);
	let commentDialogOpen = $state(false);
	let activeTagId = $state<number | null>(null);
	let commentText = $state("");

	async function linkTag(name: string) {
		const id = allTags.find((t) => t.name === name)?.id;
		if (id !== undefined) {
			onTag(id);
		}
	}
	
	async function handleUntag(id: number) {
		onUntag(id);
	}

	function handleCommandKeydown(e: KeyboardEvent) {
		if (e.key === "Enter") {
			if (allTags.some((t) => t.name === textValue)) {
				linkTag(textValue);
				value = "";
				textValue = "";
			} else {
				// Close popover before opening dialog
				dropdownOpen = false;
				dialogOpen = true;
			}
		}
	}

	async function handleCreateTag(p: {
		name: string;
		description?: string;
		tagType: TagType;
	}) {
		
		// Use the helper function
		const newTag = await createTag(p.name, p.tagType, p.description);
		
		if (newTag) {
			// Auto-link the newly created tag
			onTag(newTag.id);
			
			// Clear input and close dialog
			textValue = '';
			value = '';
		}
		
		dialogOpen = false;
	}

	function openCommentDialog(t: TagMeta) {
		activeTagId = t.id;
		commentText = (t as any).comment ?? "";
		commentDialogOpen = true;
	}

	function submitComment() {
		if (activeTagId == null) return;
		const newComment = (commentText || '').trim() || undefined;
		onUpdate?.(activeTagId, newComment);
		commentDialogOpen = false;
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="tagging-component border border-gray-300 rounded-md bg-gray-100 p-2 text-lg"
	onclick={(e) => e.stopPropagation()}
>
	<!-- Dialog with the new tag form -->
	<Dialog bind:open={dialogOpen}>
		<DialogContent portalProps={{ disabled: true }}>
			<DialogHeader>
				<DialogTitle>New Tag</DialogTitle>
				<TagEditForm {tagType} initTagName={textValue} add={handleCreateTag} />
			</DialogHeader>
		</DialogContent>
	</Dialog>

	<!-- Dialog for editing/adding a tag comment -->
	<Dialog bind:open={commentDialogOpen}>
		<DialogContent portalProps={{ disabled: true }}>
			<DialogHeader>
				<DialogTitle>Edit Tag Comment</DialogTitle>
				<div class="flex gap-2">
					<input class="input" bind:value={commentText} onkeydown={(e) => e.key === 'Enter' && submitComment()} />
					<Button onclick={submitComment}>Save</Button>
				</div>
			</DialogHeader>
		</DialogContent>
	</Dialog>

	<!-- Combobox for adding new tags -->
	<Popover bind:open={dropdownOpen}>
		<PopoverTrigger>
			<Button
				variant="outline"
				role="combobox"
				class="w-[200px] justify-between"
			>
				Add tag...
			</Button>
		</PopoverTrigger>
		<PopoverContent class="w-40" portalProps={{ disabled: true }}>
			<Command bind:value onkeydown={handleCommandKeydown}>
				<CommandInput bind:value={textValue} placeholder="Search tags..." />
				<CommandList>
					<CommandEmpty>No tags found.</CommandEmpty>
					<CommandGroup>
						{#each dropdownTags as tag}
							<CommandItem
								value={tag.name}
								onSelect={() => {
									linkTag(tag.name);
									value = tag.name;
									dropdownOpen = false;
								}}
							>
								{tag.name}
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
			{@const fullTag = tags.get(tag.id)}
			<div class="tag" onclick={() => openCommentDialog(tag)}>
				<Tooltip>
					<TooltipTrigger><span>{tag.name}</span></TooltipTrigger>
					<TooltipContent>
						{#if fullTag}
							<p>{fullTag.description}</p>
						{/if}
						{#if (tag as any).comment}
							<p>“{(tag as any).comment}”</p>
						{/if}
						<p>Tagged by {tag.tagger.name} {timeAgo(new Date(tag.date))}</p>
					</TooltipContent>
				</Tooltip>
				<button class="ml-2 hover:text-red-700" onclick={(e) => { e.stopPropagation(); handleUntag(tag.id); }}>
					<Fa icon={faSquareXmark} size="lg" />
				</button>
			</div>
		{/each}

		{#if itemTags.length > maxTags}
			<div class="tag plus-tag">
				<span>+{itemTags.length - maxTags}</span>
				<div class="overlay">
					{#each itemTags.slice(maxTags) as tag}
						<div class="tag overlay-tag">
							<span>{tag.name}</span>
						</div>
					{/each}
				</div>
			</div>
		{/if}
	</div>
</div>

<style>
	.tags-list {
		display: inline-flex;
		flex-wrap: wrap;
		/* margin-top: 1em; */
	}
	.tag {
		display: inline-flex;
		align-items: center;
		padding: 0.5em 1em;
		margin: 0 0.5em;
		border: 1px solid #ccc;
		border-radius: 20px;
		background-color: #f1f1f1;
		font-size: 0.7em;
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
</style>
