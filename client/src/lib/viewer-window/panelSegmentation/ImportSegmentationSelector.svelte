<script lang="ts">
	import { Button } from "$lib/components/ui/button/index.js";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import { converters } from "$lib/webgl/segmentationConverter";
	import { getContext } from "svelte";
	import AI from "../icons/AI.svelte";
	import {
		type Segmentation,
		type SegmentationContext,
	} from "./segmentationContext.svelte";
	import { orderSegmentationsByCreator } from "./segmentationUtils";

	interface Props {
		segmentation: Segmentation;
		segmentationContext: SegmentationContext;
		close: () => void;
		resolve: (segmentation: Segmentation) => void;
	}

	let { segmentation, segmentationContext, resolve, close }: Props = $props();

	const globalContext = getContext<GlobalContext>("globalContext");
	const user_id = globalContext.user.id;

	// Get ordered segmentations (model first, then user's own, then others - grouped by creator)
	const orderedSegmentations = $derived(
		orderSegmentationsByCreator(
			segmentationContext.modelSegmentations,
			segmentationContext.graderSegmentations,
			user_id,
		),
	);

	// Apply filtering: exclude current segmentation and check converters
	const referenceSegmentations = $derived(
		orderedSegmentations
			.filter(
				(s) =>
					!(
						s.id === segmentation.id &&
						s.annotation_type === segmentation.annotation_type
					),
			)
			.filter((other) => {
				const from = segmentation.data_representation;
				const to = other.data_representation;
				const key = `${from}->${to}`;
				return from == to || key in converters;
			}),
	);

	function _resolve(segmentation: Segmentation) {
		resolve(segmentation);
		close();
	}
</script>

{#if referenceSegmentations.length > 0}
	<div>Select segmentation to import from:</div>
	<div id="table-container">
		<table>
			<thead>
				<tr>
					<th></th>
					<th>ID</th>
					<th>Created By</th>
					<th>Feature</th>
				</tr>
			</thead>
			<tbody>
				{#each referenceSegmentations as segmentation}
					<!-- svelte-ignore a11y_click_events_have_key_events -->
					<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
					<tr onclick={() => _resolve(segmentation)}>
						<td>
							{#if segmentation.annotation_type == "model_segmentation"}
								<AI size="1em" />
							{/if}
						</td>
						<td class="annotation-id">[{segmentation.id}]</td>
						<td>{segmentation.creator.name}</td>
						<td>{segmentation.feature.name}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{:else}
	<div>No segmentations found to import from</div>
{/if}
<Button onclick={close}>Cancel</Button>

<style>
	div#table-container {
		overflow: auto;
		display: flex;
		flex: 1;
	}
	table {
		width: 100%;
		border-collapse: collapse;
	}

	th {
		text-align: left;
		padding: 8px;
		border-bottom: 2px solid rgba(0, 0, 0, 0.3);
		font-weight: bold;
		/* background-color: #f5f5f5; */
	}

	td {
		padding: 8px;
		border-bottom: 1px solid rgba(0, 0, 0, 0.2);
	}

	tr {
		cursor: pointer;
		transition: background-color 0.2s ease;
	}

	tr:hover {
		background-color: #0b666f;
		cursor: pointer;
	}

	.annotation-id {
		font-size: x-small;
		color: gray;
	}
</style>
