<script lang="ts">
	import { page } from "$app/state";
	import Button from "$lib/components/ui/button/button.svelte";
	import { ButtonGroup } from "$lib/components/ui/button-group";
	import { ChevronLeft, ChevronRight } from "@lucide/svelte";
	import { updateSubTaskComments } from "$lib/data";
	import { updateSubTask } from "$lib/data/api";
	import { toast } from "svelte-sonner";
	import { subTaskStates } from "../../types/openapi_constants";
	import type {
		SubTaskState,
		SubTaskWithImagesGET,
		TaskGET,
	} from "../../types/openapi_types";

	interface Props {
		task: TaskGET;
		subTask: SubTaskWithImagesGET;
		subTaskIndex: number;
	}

	let { task, subTask, subTaskIndex }: Props = $props();

	async function setState(state: SubTaskState) {
		await updateSubTask(subTask.id, { task_state: state });
	}

	async function handleViewTask() {
		const suffix_string = `?${page.url.searchParams.toString()}`;
		const url = new URL(
			`${window.location.origin}/tasks/${task.id}${suffix_string}`,
		);
		window.location.href = url.href;
	}

	function navigateSubtaskIndex(index: number, searchParams: URLSearchParams) {
		const currentUrl = window.location.href;
		const lastSlashIndex = currentUrl.lastIndexOf("/");
		const suffix_string = `?${searchParams.toString()}`;
		const newUrl =
			currentUrl.substring(0, lastSlashIndex + 1) + index + suffix_string;
		window.location.href = newUrl;
	}

	function navigate(delta: number) {
		const searchParams = page.url.searchParams;
		searchParams.delete("annotation");
		searchParams.delete("instances");
		navigateSubtaskIndex(subTaskIndex + delta, searchParams);
	}

	function prev() {
		navigate(-1);
	}

	function next() {
		navigate(1);
	}

	async function updateComments(comments: string) {
		try {
			await updateSubTaskComments(subTask.id, comments);
		} catch (e) {
			toast.error(String(e));
		}
	}
</script>

<div id="main">
	<div id="content">
		<div class="controls">
			Task {task.name}. Set {subTaskIndex} of {task.num_tasks}.
		</div>
		<Button variant="outline" onclick={handleViewTask}>Overview</Button>
		<div class="controls">
			<ButtonGroup orientation="horizontal">
				<Button
					variant="outline"
					size="sm"
					onclick={prev}
					disabled={subTaskIndex == 0}
					aria-label="Previous subtask"
				>
					<ChevronLeft />
					Previous
				</Button>
				<Button
					variant="outline"
					size="sm"
					onclick={next}
					disabled={subTaskIndex == task.num_tasks - 1}
					aria-label="Next subtask"
				>
					Next
					<ChevronRight />
				</Button>
			</ButtonGroup>
		</div>
		<div class="controls">
			<ButtonGroup orientation="horizontal">
				{#each subTaskStates as state}
					{@const isActive = subTask.task_state === state}
					<Button
						variant={isActive ? "default" : "outline"}
						size="sm"
						onclick={() => !isActive && setState(state)}
						aria-current={isActive ? "true" : "false"}
						class={isActive ? "font-semibold" : ""}
					>
						{state}
					</Button>
				{/each}
			</ButtonGroup>
		</div>

		<div class="comments">
			Comments:
			<textarea
				value={subTask.comments || ""}
				onchange={async (e) => {
					const target = e.target as HTMLTextAreaElement;
					await updateComments(target.value);
				}}
				class="w-full min-h-[60px] p-2 border rounded"
				placeholder="Add comments..."
			></textarea>
		</div>
	</div>
</div>

<style>
	div {
		display: flex;
	}
	div#main {
		flex: 1;
		flex-direction: column;
		margin: auto;
		padding: 1em;
	}
	div#content {
		flex: 0;
		flex-direction: column;
		margin: auto;
		padding: 2em;
		background-color: rgba(0, 0, 0, 0.8);
		color: white;
        border-radius: 1em;
	}
	div.controls {
        margin: 1em;
		align-items: center;
		justify-content: center;
	}
	div.comments {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	textarea {
		background-color: white;
		color: black;
	}
</style>
