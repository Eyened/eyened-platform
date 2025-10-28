<script lang="ts">
	import {
		AlertDialog,
		AlertDialogCancel,
		AlertDialogContent,
		AlertDialogDescription,
		AlertDialogFooter,
		AlertDialogHeader,
		AlertDialogTitle,
	} from "$lib/components/ui/alert-dialog";
	import {
		Tooltip,
		TooltipContent,
		TooltipTrigger,
	} from "$lib/components/ui/tooltip";
	import { starTag, unstarTag } from "$lib/data/api";
	import { GlobalContext } from "$lib/data/globalContext.svelte";
	import { createTag, deleteTag } from "$lib/data/helpers";
	import { tags } from "$lib/data/stores.svelte";
	import { faStar, faTrash } from "@fortawesome/free-solid-svg-icons";
	import { getContext } from "svelte";
	import Fa from "svelte-fa";
	import type { TagGET, TagType } from "../../types/openapi_types";
	import { Button } from "../components/ui/button";
	import TagEditForm from "./TagEditForm.svelte";

	let {
		tagType = "Annotation",
	}: { tagType?: TagType } = $props();

	const ctx = getContext<GlobalContext>("globalContext");

	let tagToDelete: number | null = $state(null);
	let dialogOpen = $derived(tagToDelete !== null);

	let filtered_tags = $derived(
		tags.filter((t) => t.tag_type === tagType)
			.sort((a, b) => a.name.localeCompare(b.name))
	);
	let favouriteTagIDs = $derived(new Set(ctx.userManager.starredTagIds));

	const setDialogOpen = (value: boolean) => {
		if (!value) {
			tagToDelete = null;
		}
	};
	
	function handleClickDelete(tagID: number) {
		tagToDelete = tagID;
	}

	async function handleClickStar(tagID: number) {
		if (favouriteTagIDs.has(tagID)) {
			await unstarTag(tagID);
			ctx.userManager.starredTagIds = ctx.userManager.starredTagIds.filter(
				(id) => id !== tagID,
			);
		} else {
			await starTag(tagID);
			ctx.userManager.starredTagIds = [...ctx.userManager.starredTagIds, tagID];
		}
	}

	async function handleCreateTag(payload: Partial<TagGET>) {
		await createTag(
			payload.name!,
			tagType as any,
			payload.description ?? "",
		);
	}
	
	async function handleDeleteTag() {
		if (tagToDelete === null) {
			return;
		}
		await deleteTag(tagToDelete);
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
				<Button onclick={handleDeleteTag}>Yes, Delete</Button>
			</AlertDialogFooter>
		</AlertDialogContent>
	</AlertDialog>

	<div class="border-radius-5 bg-gray-100 p-4">
		<TagEditForm {tagType} add={handleCreateTag} />
	</div>
	{#each filtered_tags as tag}
		<div
			class:!bg-orange-200={favouriteTagIDs.has(tag.id)}
			class="relative inline-flex items-center py-2 px-2 m-1 border-1 border-gray-500 rounded-lg bg-gray-200"
		>
			<button class="inline-block" onclick={() => handleClickStar(tag.id)}>
				<Fa icon={faStar} class="inline-block" />

				<Tooltip delayDuration={50}>
					<TooltipTrigger><span>{tag.name} ({tag.name}) </span></TooltipTrigger>
					<TooltipContent>
						<p>{tag.description ? tag.description : "No description"}</p>
					</TooltipContent>
				</Tooltip>
			</button>
			<button class="delete" onclick={() => handleClickDelete(tag.id)}>
				<Fa icon={faTrash} />
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
