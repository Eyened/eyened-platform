<script lang="ts">
	import { getThumbUrl } from '$lib/data-loading/utils';
	import { instances } from '$lib/data/stores.svelte';
	import { getContext } from 'svelte';
	import { tagInstance, untagInstance } from '../data/helpers';
	import Tagger from '../tags/Tagger.svelte';
	import type { BrowserContext } from './browserContext.svelte';

	interface Props {
		instanceId: number;
	}
	let { instanceId }: Props = $props();
	
	// Reactive: updates when instance in store changes!
	const instance = $derived(instances.get(instanceId)!);
	const browserContext = getContext<BrowserContext | undefined>("browserContext");

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
	};
</script>

<div class="w-[80vw] h-[80vh] flex flex-col">

	<div class="flex-shrink-0">
		<h2 class="text-2xl font-bold">
			{instance.id}
		</h2>
		<Tagger
			tagType="ImageInstance"
			tags={instance.tags ?? []}
			tag={(id) => tagInstance(instance, id)}
			untag={(id) => untagInstance(instance, id)}
			onUpdate={browserContext?.refreshSignatures}
		/>
	</div>

	<div class="flex-1 flex min-h-0">
		<div class="w-[60%]">
			<img src={getThumbUrl(instance, 540)} alt="preview" class="h-full w-full object-contain" />
		</div>
		<div class="w-[40%] overflow-y-scroll">
			
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
</div>
