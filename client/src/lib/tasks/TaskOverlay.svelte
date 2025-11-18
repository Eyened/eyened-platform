<script lang="ts">
	import { page } from "$app/state";
	import { ButtonGroup } from "$lib/components/ui/button-group";
	import Button from "$lib/components/ui/button/button.svelte";
	import { updateSubTaskComments } from "$lib/data";
	import { updateSubTask } from "$lib/data/api";
	import ChevronLeft from "@lucide/svelte/icons/chevron-left";
	import ChevronRight from "@lucide/svelte/icons/chevron-right";
	import { toast } from "svelte-sonner";
	import { subTaskStates } from "../../types/openapi_constants";
	import type {
		SubTaskState
	} from "../../types/openapi_types";
	import type { TaskContext } from "./TaskContext.svelte";
	import { TaskNavigation } from "./taskUtils.svelte";

	interface Props {
		taskContext: TaskContext;
	}

	let { taskContext }: Props = $props();

	const navigation = new TaskNavigation(taskContext);
    const { task, subTask, subTaskIndex } = taskContext;

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
		<div class="title">
			Task {task.name}. Set {subTaskIndex} of {task.num_tasks}.
		</div>
		<hr />

		<div class="controls">
			<ButtonGroup orientation="horizontal">
				<Button
					variant="outline"
					size="sm"
					onclick={() => navigation.prev()}
					disabled={navigation.prevDisabled}
					aria-label="Previous subtask"
				>
					<ChevronLeft />
					Previous
				</Button>
				<Button
					variant="outline"
					size="sm"
					onclick={() => navigation.next()}
					disabled={navigation.nextDisabled}
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
				rows="8"
				cols="80"
				value={subTask.comments || ""}
				onchange={async (e) => {
					const target = e.target as HTMLTextAreaElement;
					await updateComments(target.value);
				}}
				class="w-full min-h-[60px] p-2 border rounded"
				placeholder="Add comments..."
			></textarea>
		</div>

		<div class="controls">
			<Button variant="outline" onclick={handleViewTask}>Task overview</Button>
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
	div.title {
		font-weight: bold;
		align-self: center;
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
