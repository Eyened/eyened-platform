<script lang="ts">
	import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
	import { getContext, onDestroy } from "svelte";
	import {
		Brush,
		Enhance,
		ErodeDilate,
		PanelIcon,
		Polygon,
		Questionable,
		Redo,
		Undo,
	} from "../icons/icons";

	import Toggle from "$lib/Toggle.svelte";
	import { BrushTool } from "$lib/viewer/tools/Brush";
	import { EnhanceTool } from "$lib/viewer/tools/Enhance.svelte";
	import { PolygonTool } from "$lib/viewer/tools/Polygon";
	import BrushradiusControl from "./BrushradiusControl.svelte";

	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import type { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
	import type { SegmentationTool } from "$lib/viewer/tools/segmentation";
	import type { PaintSettings } from "$lib/webgl/mask.svelte";

	const viewerContext = getContext<ViewerContext>("viewerContext");
	const globalContext = getContext<GlobalContext>("globalContext");
	const image = viewerContext.image;
	const mainViewerContext = getContext<MainViewerContext>("mainViewerContext");
	const { segmentationContext } = mainViewerContext;

	let activeTool: undefined | SegmentationTool = $state(undefined);
	let removeTool = () => {};

	let panelActive = $derived(viewerContext.activePanels.has("Segmentation"));

	$effect(() => {
		if (!panelActive) {
			removeTool();
			activeTool = undefined;
		}
	});

	let lock = viewerContext.lockScroll;
	function activate(tool: SegmentationTool) {
		removeTool();
		if (activeTool === tool) {
			activeTool = undefined;
			removeTool = () => {};
			viewerContext.lockScroll = lock;
			return;
		}
		activeTool = tool;
		lock = viewerContext.lockScroll;
		viewerContext.lockScroll = true;
		removeTool = viewerContext.addOverlay(tool);
	}
	onDestroy(() => {
		segmentationContext.erodeDilateActive = false;
		segmentationContext.questionableActive = false;
		removeTool();
	});

	const drawingExecutor = {
		getCtx: () => image.getDrawingCtx(),
		draw: async (ctx: CanvasRenderingContext2D, mode: "paint" | "erase") => {
			const segmentationItem = segmentationContext.segmentationItem;

			// Check if a segmentation is selected
			if (!segmentationItem) {
				globalContext.dialogue =
					"No segmentation selected. Please select a segmentation to edit.";
				return;
			}

			const segmentation = segmentationItem.segmentation;

			// Check if it's a model segmentation (typically not editable directly)
			if (segmentation.annotation_type === "model_segmentation") {
				globalContext.dialogue =
					"Model segmentations cannot be edited directly. Please duplicate it first.";
				return;
			}
			// Check if user has permission to edit this segmentation
			if (!globalContext.canEdit(segmentation)) {
				globalContext.dialogue =
					"You don't have permission to edit this segmentation.";
				return;
			}

			const paintSettings: PaintSettings = {
				paint: mode == "paint",
				dilateErode: segmentationContext.erodeDilateActive,
				questionable: segmentationContext.questionableActive,
				activeIndices: segmentationContext.activeIndices,
			};

			try {
				await segmentationItem.draw(
					viewerContext.index,
					ctx.canvas,
					paintSettings,
				);
			} catch (e) {
				console.error(e);
				globalContext.dialogue =
					"Error drawing on segmentation. Check console for details.";
			}
		},
	};
	const brush = new BrushTool(
		drawingExecutor,
		viewerContext,
		segmentationContext,
	);
	const polygon = new PolygonTool(
		drawingExecutor,
		viewerContext,
		segmentationContext,
	);
	const enhance = new EnhanceTool(
		drawingExecutor,
		viewerContext,
		segmentationContext,
		globalContext,
	);
	function toggle(key: "erodeDilateActive" | "questionableActive") {
		segmentationContext[key] = !segmentationContext[key];
	}

	function undo() {
		const segmentationItem = segmentationContext.segmentationItem;
		if (!segmentationItem) {
			globalContext.dialogue = "No segmentation selected.";
			return;
		}

		const segmentation = segmentationItem.segmentation;
		if (!globalContext.canEdit(segmentation)) {
			globalContext.dialogue =
				"You don't have permission to edit this segmentation.";
			return;
		}

		segmentationItem.undo(viewerContext.index);
	}

	function redo() {
		const segmentationItem = segmentationContext.segmentationItem;
		if (!segmentationItem) {
			globalContext.dialogue = "No segmentation selected.";
			return;
		}

		const segmentation = segmentationItem.segmentation;
		if (!globalContext.canEdit(segmentation)) {
			globalContext.dialogue =
				"You don't have permission to edit this segmentation.";
			return;
		}

		segmentationItem.redo(viewerContext.index);
	}

	function checkHistory(type: "canUndo" | "canRedo") {
		const scanNr = viewerContext.index;
		const segmentationItem = segmentationContext.segmentationItem;
		if (!segmentationItem) return false;

		// Check if user has permission to edit
		const segmentation = segmentationItem.segmentation;
		if (!globalContext.canEdit(segmentation)) return false;

		const segmentationState = segmentationItem.getSegmentationState(scanNr);
		return segmentationState?.[type] ?? false;
	}

	let canUndo = $derived.by(() => checkHistory("canUndo"));
	let canRedo = $derived.by(() => checkHistory("canRedo"));

	// Check if drawing/editing is allowed
	let canEdit = $derived.by(() => {
		const segmentationItem = segmentationContext.segmentationItem;
		if (!segmentationItem) return false;

		const segmentation = segmentationItem.segmentation;
		// Can't edit model segmentations directly
		if (segmentation.annotation_type === "model_segmentation") return false;

		return globalContext.canEdit(segmentation);
	});
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="main">
	<div>
		<PanelIcon
			onclick={() => activate(brush)}
			active={activeTool == brush}
            disabled={!canEdit && activeTool != brush}
			tooltip={canEdit
				? "Brush"
				: "Select an editable segmentation to use the brush"}
			Icon={Brush}
		/>

		<PanelIcon
			onclick={() => activate(polygon)}
			active={activeTool == polygon}
			disabled={!canEdit && activeTool != polygon}
			tooltip={canEdit
				? "Polygon"
				: "Select an editable segmentation to use the polygon tool"}
			Icon={Polygon}
		/>

		{#if enhance}
			<PanelIcon
				onclick={() => activate(enhance)}
				active={activeTool == enhance}
				disabled={!canEdit && activeTool != enhance}
				tooltip={canEdit
					? "Enhance"
					: "Select an editable segmentation to use the enhance tool"}
				Icon={Enhance}
			/>
		{:else}
			<PanelIcon
				active={segmentationContext.erodeDilateActive}
				onclick={() => toggle("erodeDilateActive")}
				disabled={!canEdit && ! segmentationContext.erodeDilateActive}
				tooltip={canEdit
					? "Dilate / Erode"
					: "Select an editable segmentation to use dilate/erode"}
				Icon={ErodeDilate}
			/>
		{/if}
		<PanelIcon
			active={segmentationContext.questionableActive}
			onclick={() => toggle("questionableActive")}
			disabled={!canEdit && ! segmentationContext.questionableActive}
			tooltip={canEdit
				? "Questionable"
				: "Select an editable segmentation to mark as questionable"}
			Icon={Questionable}
		/>
		<div class="undo-redo">
			<PanelIcon
				onclick={undo}
				tooltip="Undo"
				disabled={!canUndo}
				Icon={Undo}
			/>
			<PanelIcon
				onclick={redo}
				tooltip="Redo"
				disabled={!canRedo}
				Icon={Redo}
			/>
		</div>
	</div>

	{#if activeTool && activeTool.brushRadius !== undefined}
		<div>
			<BrushradiusControl {segmentationContext} />
		</div>
	{/if}
	{#if enhance && activeTool === enhance}
		<div class="controls">
			<label>
				<span>Hardness {enhance.hardness}</span>
				<input
					type="range"
					bind:value={enhance.hardness}
					min="0"
					max="1"
					step="0.01"
				/>
			</label>

			<label>
				<span>Pressure {enhance.pressure}</span>
				<input
					type="range"
					bind:value={enhance.pressure}
					min="0"
					max="1"
					step="0.01"
				/>
			</label>
		</div>
	{/if}
	<div class="erase">
		<Toggle
			textOff="Drawing"
			textOn="Erasing"
			bind:control={segmentationContext.flipDrawErase}
			disabled={!canEdit}
		/>
	</div>
</div>

<style>
	div {
		display: flex;
	}
	div.main {
		font-size: small;
		padding: 0.2em;
		background-color: rgba(255, 255, 255, 0.1);
	}
	div.main {
		flex-direction: column;
	}
	div.erase {
		flex-direction: row;
		justify-content: center;
	}
	div.undo-redo {
		border-left: 1px solid rgba(255, 255, 255, 0.5);
	}
	div.controls {
		display: flex;
		flex-direction: column;
	}
	label {
		display: flex;
		flex-direction: column;
	}
</style>
