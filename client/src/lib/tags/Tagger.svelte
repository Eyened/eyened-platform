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
	import { tags } from "$lib/data/stores.svelte";
	import { createTag } from "$lib/data/helpers";
	import { timeAgo } from "$lib/utils";
	import { faSquareXmark } from "@fortawesome/free-solid-svg-icons";
	import Fa from "svelte-fa";
	import type { TagGET, TagMeta } from "../../types/openapi_types";
	import TagEditForm from "./TagEditForm.svelte";

	let {
		tagType,
		tags: itemTags = [],
		maxTags = 3,
		tag: onTag = (id: number) => {},
		untag: onUntag = (id: number) => {},
		onUpdate,
	}: {
		tagType: "Annotation" | "ImageInstance" | "Study";
		tags?: TagMeta[];
		maxTags?: number;
		tag?: (id: number) => void;
		untag?: (id: number) => void;
		onUpdate?: () => void | Promise<void>;
	} = $props();

	// Get all tags from store (reactive - updates when tags map changes)
	const allTagsArray = $derived(Array.from(tags.values()));
	
	// Filter by type
	const apiTagType = $derived(
		tagType === "Annotation" ? "FormAnnotation" : tagType
	);
	
	const allTags = $derived(
		allTagsArray.filter(t => t.tag_type === apiTagType)
	);

	// Build dropdown candidates (ids already in itemTags are excluded)
	const selectedIds = $derived(new Set(itemTags.map((t) => t.id)));
	const dropdownTags = $derived(allTags.filter((t) => !selectedIds.has(t.id)));
	
	let textValue = $state("");
	let value = $state("");
	let dropdownOpen = $state(false);
	let dialogOpen = $state(false);

	async function linkTag(name: string) {
		const id = allTags.find((t) => t.name === name)?.id;
		if (id !== undefined) {
			onTag(id);
			if (onUpdate) await onUpdate();
		}
	}
	
	async function handleUntag(id: number) {
		onUntag(id);
		if (onUpdate) await onUpdate();
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
		type: "Annotation" | "ImageInstance" | "Study";
	}) {
		const apiTagType = p.type === "Annotation" ? "FormAnnotation" : p.type;
		
		// Use the helper function
		const newTag = await createTag(p.name, apiTagType, p.description);
		
		if (newTag) {
			// Auto-link the newly created tag
			onTag(newTag.id);
			
			// Refresh signatures
			if (onUpdate) await onUpdate();
			
			// Clear input and close dialog
			textValue = '';
			value = '';
		}
		
		dialogOpen = false;
	}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="tagging-component border border-gray-300 rounded-md bg-gray-100 p-2"
	onclick={(e) => e.stopPropagation()}
>
	<!-- Dialog with the new tag form -->
	<Dialog bind:open={dialogOpen}>
		<DialogContent>
			<DialogHeader>
				<DialogTitle>New Tag</DialogTitle>
				<TagEditForm {tagType} initTagName={textValue} add={handleCreateTag} />
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
		<PopoverContent class="w-40">
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
			<div class="tag">
				<Tooltip>
					<TooltipTrigger><span>{tag.name}</span></TooltipTrigger>
					<TooltipContent>
						{#if fullTag}
							<p>{fullTag.description}</p>
						{/if}
						<p>Tagged by {tag.tagger.name} {timeAgo(new Date(tag.date))}</p>
					</TooltipContent>
				</Tooltip>
				<button class="ml-2 hover:text-red-700" onclick={() => handleUntag(tag.id)}>
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
