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
	<Dialog.Content class="w-[80vw] h-[80vh] align-top">
		<div class="flex h-full">
			<div class="basis-[60%] h-full overflow-hidden flex items-center justify-center p-4">
				<img src={getThumbUrl(instance, 540)} alt="preview" class="h-full w-full object-contain" />
			</div>
			<div class="basis-[40%] h-full flex flex-col overflow-hidden">
				<Dialog.Header class="relative shrink-0 p-4">
					{instance.id}
				</Dialog.Header>
				<div class="flex-1 overflow-auto p-4">
					<table class="w-full text-sm table-fixed border-collapse text-gray-500">
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
				</div>
			</div>
		</div>
	</Dialog.Content>
</Dialog.Root>


<style>

</style>
