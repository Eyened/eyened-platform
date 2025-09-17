<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog';
	import { getThumbUrl } from '$lib/data-loading/utils';
	import { getContext } from 'svelte';
	import type { InstanceGET } from '../../types/openapi_types';
	import type { GlobalContext } from '../data/globalContext.svelte';

	const {userManager} = getContext<GlobalContext>('globalContext')

	interface Props {
		open: boolean;
		instance: InstanceGET;
	}
	let { instance, open = $bindable(false) }: Props = $props();

	const flattenToDotPaths = (
    input: Record<string, unknown> | unknown[]
        ): Record<string, unknown> => {
        const out: Record<string, unknown> = {};

        const walk = (value: unknown, path: string): void => {
            if (Array.isArray(value)) {
            if (value.length === 0 && path) {
                out[path] = [];
                return;
            }
            value.forEach((item, idx) => {
                const next = path ? `${path}.${idx}` : `${idx}`;
                walk(item, next);
            });
            } else if (value !== null && typeof value === 'object') {
            const entries = Object.entries(value as Record<string, unknown>);
            if (entries.length === 0 && path) {
                out[path] = {};
                return;
            }
            for (const [k, v] of entries) {
                const next = path ? `${path}.${k}` : k;
                walk(v, next);
            }
            } else {
            if (path) out[path] = value as unknown;
            }
        };

        walk(input, '');
        return out;
        }
</script>

<Dialog.Root bind:open={open}>
	<Dialog.Content class="min-w-[80vw] min-h-[85vh] align-top">
		<Dialog.Header class="relative">
			{instance.id}
		</Dialog.Header>

		<div class="flex flex-col flex-1 p-4">
		<div class="img-preview">
			<img src={getThumbUrl(instance, 540)} alt="preview" />
		</div>
		<table class="text-sm table-fixed border-collapse text-gray-500">
			<thead>
				<tr>
					<th class="text-black font-bold">Property</th>
					<th class="text-black font-bold">Value</th>
				</tr>
			</thead>
			<tbody>
				{#each Object.entries(flattenToDotPaths(instance)) as [key, value]}
					<tr class="odd:bg-gray-100 even:bg-gray-200 hover:bg-white">
						<td class="break-all p-1 border-t border-gray-400">{key}</td>
						<!-- Not sure if this is the way to go, but it's a quick fix -->
						<td class="break-all p-1 border-t border-gray-400">
							{#if value == null}
								NULL
							{:else if typeof value === 'object' && value !== null}
								<pre>{JSON.stringify(value, null, 2)}</pre>
							{:else}
								{value}
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
		<!-- <InstanceSegmentationTable {instance} /> -->
		</div>
	</Dialog.Content>
</Dialog.Root>


<style>

</style>
