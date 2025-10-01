<script lang="ts">
  import * as AlertDialog from "$lib/components/ui/alert-dialog";
  import * as Dialog from "$lib/components/ui/dialog";
  import type { FeatureObject } from "$lib/data/objects.svelte";
  import type { FeaturePATCH } from "../../types/openapi_types";
  import FeatureForm from "./FeatureForm.svelte";

  let { feature }: { feature: FeatureObject } = $props();
  let editOpen = $state(false);
  let deleteOpen = $state(false);

  async function handleEditSubmit(payload: FeaturePATCH) {
    await feature.save(payload);
    editOpen = false;
  }
  async function confirmDelete() {
    await feature.destroy();
    deleteOpen = false;
  }
</script>

<div class="flex gap-2">
  <button class="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700" onclick={() => (editOpen = true)}>Edit</button>
  <button class="bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700" onclick={() => (deleteOpen = true)}>Delete</button>
</div>

<Dialog.Root bind:open={editOpen}>
  <Dialog.Content>
    <Dialog.Header>
      <Dialog.Title>Edit Feature</Dialog.Title>
      <Dialog.Description>Update this feature.</Dialog.Description>
    </Dialog.Header>
    <FeatureForm feature={feature} onsubmit={handleEditSubmit} />
    <Dialog.Footer>
      <Dialog.Close class="bg-gray-500 text-white px-3 py-1 rounded hover:bg-gray-600">Close</Dialog.Close>
    </Dialog.Footer>
  </Dialog.Content>
</Dialog.Root>

<AlertDialog.Root bind:open={deleteOpen}>
  <AlertDialog.Content>
    <AlertDialog.Header>
      <AlertDialog.Title>Delete Feature</AlertDialog.Title>
      <AlertDialog.Description>
        Delete "{feature.$.name}"? This action cannot be undone.
      </AlertDialog.Description>
    </AlertDialog.Header>
    <AlertDialog.Footer>
      <AlertDialog.Cancel onclick={() => (deleteOpen = false)}>Cancel</AlertDialog.Cancel>
      <AlertDialog.Action onclick={confirmDelete}>Delete</AlertDialog.Action>
    </AlertDialog.Footer>
  </AlertDialog.Content>
</AlertDialog.Root>
