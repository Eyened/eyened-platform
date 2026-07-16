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
            class="rounded border px-2 py-1 text-sm hover:bg-gray-50"
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
            <Dialog.Overlay class="fixed inset-0 bg-black/50" />
            <Dialog.Content
                class="fixed top-1/2 left-1/2 w-[400px] -translate-x-1/2 -translate-y-1/2 rounded-lg bg-white p-6 shadow-lg"
            >
                <Dialog.Title class="mb-4 text-lg font-semibold"
                    >Edit Task</Dialog.Title
                >

                <div class="flex flex-col gap-4">
                    <div>
                        <label
                            for="task-name"
                            class="mb-1 block text-sm font-medium">Name</label
                        >
                        <input
                            id="task-name"
                            bind:value={name}
                            class="w-full rounded border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                            placeholder="Task name"
                        />
                    </div>

                    <div>
                        <label
                            for="task-description"
                            class="mb-1 block text-sm font-medium"
                            >Description</label
                        >
                        <textarea
                            id="task-description"
                            bind:value={description}
                            class="w-full rounded border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                            placeholder="Task description"
                            rows="3"
                        ></textarea>
                    </div>

                    <div>
                        <label class="mb-1 block text-sm font-medium"
                            >State</label
                        >
                        <Select.Root
                            type="single"
                            bind:value={task_state as unknown as string}
                        >
                            <Select.Trigger
                                class="w-full rounded border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                            >
                                {task_state ?? "Select state"}
                            </Select.Trigger>
                            <Select.Content
                                class="z-50 max-h-60 overflow-auto rounded border border-gray-300 bg-white shadow-lg"
                            >
                                {#each TASK_STATE_OPTIONS as state (state)}
                                    <Select.Item
                                        value={state}
                                        label={state}
                                        class="cursor-pointer rounded px-3 py-2 hover:bg-gray-100"
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
                        class="rounded border border-gray-300 px-4 py-2 hover:bg-gray-50"
                    >
                        Cancel
                    </Dialog.Close>
                    <button
                        onclick={doSave}
                        class="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
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
            <AlertDialog.Overlay class="fixed inset-0 bg-black/50" />
            <AlertDialog.Content
                class="fixed top-1/2 left-1/2 w-[380px] -translate-x-1/2 -translate-y-1/2 rounded-lg bg-white p-6 shadow-lg"
            >
                <AlertDialog.Title class="mb-2 text-lg font-semibold"
                    >Delete Task</AlertDialog.Title
                >
                <AlertDialog.Description class="mb-6 text-gray-600">
                    This action cannot be undone. Delete "{task.name}"?
                </AlertDialog.Description>

                <div class="flex justify-end gap-2">
                    <AlertDialog.Cancel
                        class="rounded border border-gray-300 px-4 py-2 hover:bg-gray-50"
                    >
                        Cancel
                    </AlertDialog.Cancel>
                    <AlertDialog.Action
                        onclick={doDelete}
                        class="rounded bg-red-600 px-4 py-2 text-white hover:bg-red-700"
                    >
                        Delete
                    </AlertDialog.Action>
                </div>
            </AlertDialog.Content>
        </AlertDialog.Portal>
    </AlertDialog.Root>
</div>
