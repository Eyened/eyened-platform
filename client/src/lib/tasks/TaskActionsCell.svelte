<script lang="ts">
    import * as AlertDialog from "$lib/components/ui/alert-dialog";
    import * as Dialog from "$lib/components/ui/dialog";
    import * as DropdownMenu from "$lib/components/ui/dropdown-menu";
    import * as Select from "$lib/components/ui/select";
    import type { TaskGET, TaskState } from "../../types/openapi_types";
    import { TASK_STATE_OPTIONS } from "$lib/openapi/enums";
    import { updateTask, deleteTask } from "$lib/data/helpers";

    let { task }: { task: TaskGET } = $props();

    let openEdit = $state(false);
    let openDelete = $state(false);
    let name = $state(task.name);
    let description = $state(task.description ?? "");
    let task_state = $state<TaskState | undefined>(
        task.task_state ?? undefined,
    );

    async function doSave() {
        await updateTask(task.id, {
            name,
            description,
            task_state: task_state ?? null,
        });
        openEdit = false;
    }

    async function doDelete() {
        await deleteTask(task.id);
        openDelete = false;
    }

    function openEditDialog() {
        name = task.name;
        description = task.description ?? "";
        task_state = task.task_state ?? undefined;
        openEdit = true;
    }

    function openDeleteDialog() {
        openDelete = true;
    }
</script>

<div class="flex justify-end">
    <DropdownMenu.Root>
        <DropdownMenu.Trigger
            class="rounded text-sm hover:bg-gray-50 border px-2 py-1"
        >
            ...
        </DropdownMenu.Trigger>
        <DropdownMenu.Content align="end">
            <DropdownMenu.Item onclick={openEditDialog}>Edit</DropdownMenu.Item>
            <DropdownMenu.Item onclick={openDeleteDialog} class="text-red-600">
                Delete
            </DropdownMenu.Item>
        </DropdownMenu.Content>
    </DropdownMenu.Root>

    <!-- Edit Dialog -->
    <Dialog.Root bind:open={openEdit}>
        <Dialog.Portal>
            <Dialog.Overlay class="bg-black/50 fixed inset-0" />
            <Dialog.Content
                class="rounded-lg bg-white shadow-lg fixed top-1/2 left-1/2 w-[400px] -translate-x-1/2 -translate-y-1/2 p-6"
            >
                <Dialog.Title class="text-lg font-semibold mb-4"
                    >Edit Task</Dialog.Title
                >

                <div class="flex flex-col gap-4">
                    <div>
                        <label
                            for="task-name"
                            class="text-sm font-medium mb-1 block">Name</label
                        >
                        <input
                            id="task-name"
                            bind:value={name}
                            class="rounded border-gray-300 focus:ring-blue-500 w-full border px-3 py-2 focus:ring-2 focus:outline-none"
                            placeholder="Task name"
                        />
                    </div>

                    <div>
                        <label
                            for="task-description"
                            class="text-sm font-medium mb-1 block"
                            >Description</label
                        >
                        <textarea
                            id="task-description"
                            bind:value={description}
                            class="rounded border-gray-300 focus:ring-blue-500 w-full border px-3 py-2 focus:ring-2 focus:outline-none"
                            placeholder="Task description"
                            rows="3"
                        ></textarea>
                    </div>

                    <div>
                        <label class="text-sm font-medium mb-1 block"
                            >State</label
                        >
                        <Select.Root
                            type="single"
                            bind:value={task_state as unknown as string}
                        >
                            <Select.Trigger
                                class="rounded border-gray-300 focus:ring-blue-500 w-full border px-3 py-2 focus:ring-2 focus:outline-none"
                            >
                                {task_state ?? "Select state"}
                            </Select.Trigger>
                            <Select.Content
                                class="rounded border-gray-300 bg-white shadow-lg z-50 max-h-60 overflow-auto border"
                            >
                                {#each TASK_STATE_OPTIONS as state (state)}
                                    <Select.Item
                                        value={state}
                                        label={state}
                                        class="rounded hover:bg-gray-100 cursor-pointer px-3 py-2"
                                    >
                                        {state}
                                    </Select.Item>
                                {/each}
                            </Select.Content>
                        </Select.Root>
                    </div>
                </div>

                <div class="mt-6 flex justify-end gap-2">
                    <Dialog.Close
                        class="rounded border-gray-300 hover:bg-gray-50 border px-4 py-2"
                    >
                        Cancel
                    </Dialog.Close>
                    <button
                        onclick={doSave}
                        class="rounded bg-blue-600 text-white hover:bg-blue-700 px-4 py-2"
                    >
                        Save
                    </button>
                </div>
            </Dialog.Content>
        </Dialog.Portal>
    </Dialog.Root>

    <!-- Delete Alert Dialog -->
    <AlertDialog.Root bind:open={openDelete}>
        <AlertDialog.Portal>
            <AlertDialog.Overlay class="bg-black/50 fixed inset-0" />
            <AlertDialog.Content
                class="rounded-lg bg-white shadow-lg fixed top-1/2 left-1/2 w-[380px] -translate-x-1/2 -translate-y-1/2 p-6"
            >
                <AlertDialog.Title class="text-lg font-semibold mb-2"
                    >Delete Task</AlertDialog.Title
                >
                <AlertDialog.Description class="text-gray-600 mb-6">
                    This action cannot be undone. Delete "{task.name}"?
                </AlertDialog.Description>

                <div class="flex justify-end gap-2">
                    <AlertDialog.Cancel
                        class="rounded border-gray-300 hover:bg-gray-50 border px-4 py-2"
                    >
                        Cancel
                    </AlertDialog.Cancel>
                    <AlertDialog.Action
                        onclick={doDelete}
                        class="rounded bg-red-600 text-white hover:bg-red-700 px-4 py-2"
                    >
                        Delete
                    </AlertDialog.Action>
                </div>
            </AlertDialog.Content>
        </AlertDialog.Portal>
    </AlertDialog.Root>
</div>
