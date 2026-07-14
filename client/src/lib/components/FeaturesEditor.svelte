<script lang="ts">
    import * as Dialog from "$lib/components/ui/dialog";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { createFeature } from "$lib/data/helpers";
    import { getContext } from "svelte";
    import type { FeaturePATCH, FeaturePUT } from "../../types/openapi_types";
    import FeatureForm from "./FeatureForm.svelte";
    import FeaturesTable from "./FeaturesTable.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");
    let createOpen = $state(false);

    async function handleCreate(payload: FeaturePATCH) {
        await createFeature({
            name: payload.name!,
            subfeature_ids: payload.subfeature_ids ?? null,
        } as FeaturePUT);
        createOpen = false;
    }
</script>

<div class="p-4">
    <div class="mb-4 flex items-center justify-between">
        <h2 class="text-2xl font-bold">Features</h2>
        <button
            onclick={() => (createOpen = true)}
            class="rounded bg-green-600 px-4 py-2 text-white hover:bg-green-700"
        >
            Add Feature
        </button>
    </div>

    <Dialog.Root bind:open={createOpen}>
        <Dialog.Content>
            <Dialog.Header>
                <Dialog.Title>Create Feature</Dialog.Title>
                <Dialog.Description
                    >Set a name and subfeatures.</Dialog.Description
                >
            </Dialog.Header>
            <FeatureForm onsubmit={handleCreate} />
            <Dialog.Footer>
                <Dialog.Close
                    class="rounded bg-gray-500 px-3 py-1 text-white hover:bg-gray-600"
                    >Close</Dialog.Close
                >
            </Dialog.Footer>
        </Dialog.Content>
    </Dialog.Root>

    <FeaturesTable />
</div>
