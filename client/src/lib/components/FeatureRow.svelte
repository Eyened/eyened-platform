<script lang="ts">
  import * as AlertDialog from "$lib/components/ui/alert-dialog";
  import * as Dialog from "$lib/components/ui/dialog";
  import { Button } from "$lib/components/ui/button";
  import type { FeatureGET, FeaturePATCH } from "../../types/openapi_types";
  import { updateFeature, deleteFeature } from "$lib/data/helpers";
  import FeatureForm from "./FeatureForm.svelte";

  let { feature }: { feature: FeatureGET } = $props();
  let editOpen = $state(false);
  let deleteOpen = $state(false);

  async function handleEditSubmit(payload: FeaturePATCH) {
    await updateFeature(feature.id, payload);
    editOpen = false;
  }
  async function confirmDelete() {
    await deleteFeature(feature.id);
    deleteOpen = false;
  }
</script>

<div class="flex gap-2">
  <Button variant="outline" size="sm" onclick={() => (editOpen = true)}>Edit</Button>
  <Button variant="destructive" size="sm" onclick={() => (deleteOpen = true)}>Delete</Button>
</div>

<Dialog.Root bind:open={editOpen}>
  <Dialog.Content>
    <Dialog.Header>
      <Dialog.Title>Edit Feature</Dialog.Title>
      <Dialog.Description>Update this feature.</Dialog.Description>
    </Dialog.Header>
    <FeatureForm {feature} onsubmit={handleEditSubmit} />
    <Dialog.Footer>
      <Button variant="outline" onclick={() => (editOpen = false)}>Close</Button>
    </Dialog.Footer>
  </Dialog.Content>
</Dialog.Root>

<AlertDialog.Root bind:open={deleteOpen}>
  <AlertDialog.Content>
    <AlertDialog.Header>
      <AlertDialog.Title>Delete Feature</AlertDialog.Title>
      <AlertDialog.Description>
        Delete "{feature.name}"? This action cannot be undone.
      </AlertDialog.Description>
    </AlertDialog.Header>
    <AlertDialog.Footer>
      <AlertDialog.Cancel>Cancel</AlertDialog.Cancel>
      <Button variant="destructive" onclick={confirmDelete}>Delete</Button>
    </AlertDialog.Footer>
  </AlertDialog.Content>
</AlertDialog.Root>
