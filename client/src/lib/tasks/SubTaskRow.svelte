<script lang="ts">
  import { page } from "$app/state";
  import InstanceComponent from "$lib/browser/InstanceComponent.svelte";
  import { Button } from "$lib/components/ui/button";
  import * as Input from "$lib/components/ui/input";
  import * as Table from "$lib/components/ui/table";
  import type { SubTaskObject } from "$lib/data/objects.svelte";
  import { toast } from "svelte-sonner";

  type Props = {
    obj: SubTaskObject;
    taskId: number;
    index: number;
    start: number;
  };
  let { obj, taskId, index, start }: Props = $props();

  const row = $derived(obj.$);
  let newInstanceId = $state<string>("");

  function handleGrade() {
    const suffix_string = `?${page.url.searchParams.toString()}`;
    const absoluteIndex = index + start;
    const url = new URL(`${window.location.origin}/tasks/${taskId}/grade/${absoluteIndex}${suffix_string}`);
    window.location.href = url.href;
  }

  async function addImage() {
    try {
      const id = Number(newInstanceId);
      if (!id) {
        toast.error("Please enter a valid instance id");
        return;
      }
      await obj.addImage(id);
      newInstanceId = "";
    } catch (e) {
      toast.error(String(e));
    }
  }

  async function removeImage(instance_id: number) {
    try {
      await obj.removeImage(instance_id);
    } catch (e) {
      toast.error(String(e));
    }
  }

  async function updateComments(comments: string) {
    try {
      await obj.setComments(comments);
    } catch (e) {
      toast.error(String(e));
    }
  }
</script>

<Table.Row>
  <Table.Cell>{row.id}</Table.Cell>
  <Table.Cell>{row.task_state ?? "-"}</Table.Cell>
  <Table.Cell>
    <Button
      href={`${window.location.origin}/tasks/${taskId}/grade/${row.index}`}
      class="px-2 py-1 bg-blue-500 text-white rounded hover:bg-blue-600"
    >
      View
    </Button>
  </Table.Cell>
  <Table.Cell>
    <div class="instances flex flex-wrap gap-1">
      {#if (row as any).images?.length > 0}
        {#each (row as any).images as img}
          <div class="relative inline-block">
            <InstanceComponent instance={img} />
            <button
              class="absolute -top-1 -right-1 z-10 h-6 w-6 rounded-full bg-red-600 text-white text-xs leading-6 text-center shadow hover:bg-red-700"
              onclick={(e) => { e.stopPropagation(); removeImage(img.id); }}
              aria-label="Remove image"
              title="Remove image"
            >
              ×
            </button>
          </div>
        {/each}
      {:else}
        -
      {/if}

      <div class="flex items-center gap-2 mt-1 w-full">
        <Input.Root type="number" bind:value={newInstanceId} placeholder="Instance ID" class="w-36" />
        <Button onclick={addImage}>
          Add Image
        </Button>
      </div>
    </div>
  </Table.Cell>
  <Table.Cell>
    <textarea
      value={row.comments || ""}
      onchange={async (e) => {
        const target = e.target as HTMLTextAreaElement;
        await updateComments(target.value);
      }}
      class="w-full min-h-[60px] p-2 border rounded"
      placeholder="Add comments..."
    ></textarea>
  </Table.Cell>
</Table.Row>

<style>
  .instances { display: flex; flex-wrap: wrap; gap: 4px; }
</style>
