<script lang="ts">
	import { Button } from "$lib/components/ui/button";
	import { features } from "$lib/data";
	import { fetchSegmentation } from "$lib/data/api";
	import AI from "../icons/AI.svelte";
	import { Close, Draw } from "../icons/icons";
	import type { GlobalContext } from "$lib/data/globalContext.svelte";
	import { apiErrorFromResponse, fetchApi } from "$lib/api/client";
	import { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
	import { SemiAutoPointTool, type PromptPoint } from "$lib/viewer/tools/SemiAutoPoints";
	import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
	import ChevronDownIcon from "@lucide/svelte/icons/chevron-down";
	import ChevronRightIcon from "@lucide/svelte/icons/chevron-right";
	import { getContext, onDestroy } from "svelte";
	import { toast } from "svelte-sonner";

	const globalContext = getContext<GlobalContext>("globalContext");
	const viewerContext = getContext<ViewerContext>("viewerContext");
	const mainViewerContext = getContext<MainViewerContext>("mainViewerContext");
	const segmentationContext = mainViewerContext.segmentationContext;

	type Mode = "area" | "layer";
	type Strength = "light" | "medium" | "strong";

	let mode = $state<Mode>("area");
	let smoothingStrength = $state<Strength>("medium");
	let positiveBoostStrength = $state<Strength>("strong");
	let negativeGuardRadius = $state(6);
	let positiveAnchorRadius = $state(4);
	let selectedFeatureId = $state<number | undefined>(undefined);
	let sliceIndex = $state(0);

	let positivePoints = $state<PromptPoint[]>([]);
	let negativePoints = $state<PromptPoint[]>([]);
	let captureActive = $state(false);

	let running = $state(false);
	let progress = $state(0);
	let progressMessage = $state("");
	let expanded = $state(true);

	let removeOverlay: (() => void) | undefined;
	const pointTool = new SemiAutoPointTool({
		getPositive: () => positivePoints,
		getNegative: () => negativePoints,
		setPoints: (positive, negative) => {
			positivePoints = positive;
			negativePoints = negative;
		},
	});

	const featureOptions = $derived(
		features
			.map((f) => f)
			.sort((a, b) => a.name.localeCompare(b.name)),
	);

	$effect(() => {
		if (featureOptions.length > 0 && selectedFeatureId == null) {
			selectedFeatureId = featureOptions[0].id;
		}
	});

	$effect(() => {
		sliceIndex = viewerContext.index;
	});

	function toggleCapture() {
		if (captureActive) {
			removeOverlay?.();
			removeOverlay = undefined;
			captureActive = false;
			return;
		}
		removeOverlay?.();
		removeOverlay = viewerContext.addOverlay(pointTool);
		captureActive = true;
	}

	function clearPoints() {
		positivePoints = [];
		negativePoints = [];
	}

	async function startSemiAuto() {
		if (running) return;
		if (!selectedFeatureId) {
			toast.error("Select a feature for the generated segmentation");
			return;
		}
		if (positivePoints.length === 0) {
			toast.error("Add at least one positive point");
			return;
		}

		running = true;
		progress = 0;
		progressMessage = "Submitting job";
		globalContext.dialogue = "Submitting semi-auto segmentation job...";

		try {
			const startResp = await fetchApi("/segmentations/semi-auto", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					image_id: viewerContext.instance.id,
					feature_id: Number(selectedFeatureId),
					mode,
					slice_index: Math.max(0, Number(sliceIndex) || 0),
					positive_points: positivePoints.map((p) => ({ x: p.x, y: p.y })),
					negative_points: negativePoints.map((p) => ({ x: p.x, y: p.y })),
					smoothing_strength: smoothingStrength,
					negative_guard_radius: Math.max(1, Number(negativeGuardRadius) || 1),
					positive_boost_strength: positiveBoostStrength,
					positive_anchor_radius: Math.max(1, Number(positiveAnchorRadius) || 1),
				}),
			});
			if (!startResp.ok) {
				throw await apiErrorFromResponse(startResp);
			}
			const started = await startResp.json();
			const jobId = started.job_id as string;

			const startedAt = Date.now();
			const timeoutMs = 12 * 60 * 1000;
			let missingStatusCount = 0;

			while (true) {
				if (Date.now() - startedAt > timeoutMs) {
					throw new Error("Semi-auto segmentation timed out");
				}

				await new Promise((resolve) => setTimeout(resolve, 1200));
				const statusResp = await fetchApi(`/segmentations/semi-auto/status/${jobId}`);
				if (statusResp.status === 404) {
					missingStatusCount += 1;
					progressMessage = "Waiting for job status registration...";
					globalContext.dialogue = progressMessage;
					if (missingStatusCount <= 20) {
						continue;
					}
				}
				if (!statusResp.ok) {
					throw await apiErrorFromResponse(statusResp);
				}
				const status = await statusResp.json();
				missingStatusCount = 0;
				progress = Math.max(0, Math.min(1, Number(status.progress) || 0));
				progressMessage = String(status.message || "Working...");
				globalContext.dialogue = `${progressMessage} (${Math.round(progress * 100)}%)`;

				if (status.status === "failed") {
					throw new Error(String(status.error || "Semi-auto segmentation failed"));
				}

				if (status.status === "finished") {
					const segmentationId = status.result?.segmentation_id;
					if (!segmentationId) {
						throw new Error("Job finished without segmentation id");
					}
					const segmentation = await fetchSegmentation(Number(segmentationId));
					segmentationContext.activateForDrawing(segmentation, globalContext.user.id);
					toast.success("Semi-auto segmentation created");
					break;
				}
			}
		} catch (err) {
			console.error(err);
			toast.error(err instanceof Error ? err.message : "Semi-auto segmentation failed");
		} finally {
			running = false;
			globalContext.dialogue = null;
		}
	}

	onDestroy(() => {
		removeOverlay?.();
		removeOverlay = undefined;
	});
</script>

<div class="semi-auto-card">
	<div class="header-row">
		<div class="title">Semi-auto segmentation</div>
		<div class="header-controls">
			<div class="point-counts">
				<span>+ {positivePoints.length}</span>
				<span>- {negativePoints.length}</span>
			</div>
			<button
				class="collapse-btn"
				type="button"
				onclick={() => (expanded = !expanded)}
				aria-expanded={expanded}
				aria-label={expanded ? "Collapse semi-auto panel" : "Expand semi-auto panel"}
			>
				{#if expanded}
					<ChevronDownIcon size={14} />
				{:else}
					<ChevronRightIcon size={14} />
				{/if}
			</button>
		</div>
	</div>

	{#if expanded}
		<div class="grid">
			<label>
				Mode
				<select bind:value={mode}>
					<option value="area">Area (prompt region)</option>
					<option value="layer">Layer (full layer trace)</option>
				</select>
			</label>

			<label>
				Feature
				<select bind:value={selectedFeatureId}>
					{#each featureOptions as feature}
						<option value={feature.id}>{feature.name}</option>
					{/each}
				</select>
			</label>

			<label>
				Slice index
				<input type="number" min="0" bind:value={sliceIndex} />
			</label>

			<label>
				Smoothing
				<select bind:value={smoothingStrength}>
					<option value="light">Light</option>
					<option value="medium">Medium</option>
					<option value="strong">Strong</option>
				</select>
			</label>

			<label>
				Positive strength
				<select bind:value={positiveBoostStrength}>
					<option value="light">Light</option>
					<option value="medium">Medium</option>
					<option value="strong">Strong</option>
				</select>
			</label>

			<label>
				Negative point radius
				<input type="number" min="1" max="64" bind:value={negativeGuardRadius} />
			</label>

			<label>
				Positive anchor radius
				<input type="number" min="1" max="64" bind:value={positiveAnchorRadius} />
			</label>
		</div>

		<div class="actions">
			<Button
				variant={captureActive ? "default" : "outline"}
				size="sm"
				class="action-btn"
				onclick={toggleCapture}
			>
				<span class="btn-content">
					<Draw size="1em" />
					<span>{captureActive ? "Stop point capture" : "Capture points"}</span>
				</span>
			</Button>
			<Button variant="outline" size="sm" class="action-btn" onclick={clearPoints} disabled={running}>
				<span class="btn-content">
					<Close size="1em" />
					<span>Clear points</span>
				</span>
			</Button>
			<Button size="sm" class="action-btn" onclick={startSemiAuto} disabled={running || positivePoints.length === 0}>
				<span class="btn-content">
					<AI size="1em" />
					<span>{running ? "Running..." : "Run semi-auto"}</span>
				</span>
			</Button>
		</div>

		{#if running}
			<div class="progress-alert" role="status" aria-live="polite">
				<div>{progressMessage || "Running..."}</div>
				<div>{Math.round(progress * 100)}%</div>
			</div>
		{/if}
	{/if}
</div>

<style>
	.semi-auto-card {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0.6rem;
		margin: 0.35rem 0.25rem 0.6rem;
		border: 1px solid rgba(114, 229, 255, 0.35);
		background: rgba(0, 80, 110, 0.22);
		border-radius: 0.5rem;
	}
	.header-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		padding: 0.2rem 0.1rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.14);
	}
	.header-controls {
		display: flex;
		align-items: center;
		gap: 0.45rem;
	}
	.title {
		font-size: 0.86rem;
		font-weight: 600;
	}
	.point-counts {
		display: flex;
		gap: 0.5rem;
		font-size: 0.8rem;
		opacity: 0.9;
	}
	.collapse-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.45rem;
		height: 1.45rem;
		border: 1px solid rgba(255, 255, 255, 0.2);
		background: rgba(255, 255, 255, 0.06);
		color: inherit;
		padding: 0;
		border-radius: 0.3rem;
		cursor: pointer;
	}
	.collapse-btn:hover {
		background: rgba(255, 255, 255, 0.12);
	}
	.collapse-btn:focus-visible {
		outline: 2px solid rgba(114, 229, 255, 0.65);
		outline-offset: 1px;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.4rem 0.6rem;
	}
	label {
		display: flex;
		flex-direction: column;
		font-size: 0.78rem;
		gap: 0.2rem;
	}
	input,
	select {
		font-size: 0.8rem;
		padding: 0.2rem 0.3rem;
		border-radius: 0.3rem;
		border: 1px solid rgba(255, 255, 255, 0.25);
		background: rgba(0, 0, 0, 0.15);
		color: inherit;
	}
	.actions {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.35rem;
	}
	.action-btn {
		width: 100%;
	}
	.btn-content {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.4rem;
		width: 100%;
	}
	.progress-alert {
		display: flex;
		justify-content: space-between;
		font-size: 0.8rem;
		padding: 0.35rem 0.45rem;
		border: 1px solid rgba(255, 255, 255, 0.2);
		border-radius: 0.35rem;
		background: rgba(255, 255, 255, 0.08);
	}
</style>
