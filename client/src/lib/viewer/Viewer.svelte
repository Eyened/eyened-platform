<script lang="ts">
	import type { EventName } from './viewer-utils';
	import type { ViewerContext } from './viewerContext.svelte';
	import { getContext, onDestroy, onMount } from 'svelte';
	import { ViewerWindowContext } from '$lib/viewer-window/viewerWindowContext.svelte';
	import Stretch from '$lib/viewer-window/panelRendering/Stretch.svelte';
	import WindowLevel from '$lib/viewer-window/panelRendering/WindowLevel.svelte';

	export interface Props {
		showInfo?: boolean;
	}
	let { showInfo = true }: Props = $props();

	const viewerContext = getContext<ViewerContext>('viewerContext');
	const viewerWindowContext = getContext<ViewerWindowContext>('viewerWindowContext');

	// add viewer to viewerWindowContext
	// this registers the viewerContext for repaint callbacks
	onDestroy(viewerWindowContext.addViewer(viewerContext));

	let viewerElement: HTMLDivElement;

	// update viewingRect and canvas size on resize
	onMount(() => {
		const resizeObserver = new ResizeObserver(() => {
			const viewingRect = viewerElement.getBoundingClientRect();
			viewerContext.viewingRect = viewingRect;
			const { width, height } = viewingRect;
			viewerContext.canvas2D.width = width;
			viewerContext.canvas2D.height = height;
			viewerContext.viewerSize = { width, height };
			viewerContext.initTransform();
		});

		resizeObserver.observe(viewerElement);

		return () => resizeObserver.disconnect();
	});

	//
	onMount(() => {
		viewerElement.appendChild(viewerContext.canvas2D);
	});

	// event handling
	let cursor = {
		x: 0,
		y: 0
	};

	let pointerDown = false;
	function forwardEvent(eventName: EventName, event: Event) {
		const position = viewerContext.viewerToImageCoordinates(cursor);
		viewerContext.forwardEvent(eventName, { event, viewerContext, cursor, position });
	}

	function onpointerenter(e: PointerEvent) {
		viewerElement.focus();
		viewerContext.active = true;
		forwardEvent('pointerenter', e);
	}

	function onpointerleave(e: PointerEvent) {
		if (!pointerDown) {
			viewerContext.active = false;
		}
		forwardEvent('pointerleave', e);
	}

	function onpointerdown(e: PointerEvent) {
		// Capture the pointer to ensure we get all events even if the pointer moves outside the viewer until the pointer is released
		viewerElement.setPointerCapture(e.pointerId);
		pointerDown = true;
		forwardEvent('pointerdown', e);
	}

	function onpointerup(e: PointerEvent) {
		// Release the pointer
		viewerElement.releasePointerCapture(e.pointerId);
		pointerDown = false;
		forwardEvent('pointerup', e);
	}

	function onkeydown(e: KeyboardEvent) {
		forwardEvent('keydown', e);
	}

	function onkeyup(e: KeyboardEvent) {
		forwardEvent('keyup', e);
	}

	function onpointermove(e: PointerEvent) {
		cursor = {
			x: e.x - viewerContext.viewingRect.left,
			y: e.y - viewerContext.viewingRect.top
		};
		forwardEvent('pointermove', e);
	}

	function onwheel(e: WheelEvent) {
		forwardEvent('wheel', e);
	}

	function ondblclick(e: MouseEvent) {
		forwardEvent('dblclick', e);
	}

	function oncontextmenu(e: MouseEvent) {
		e.preventDefault();
	}

	let index = $state({
		get value() {
			return viewerContext.index;
		},
		set value(value: number) {
			viewerContext.setIndex(value);
		}
	});
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div class="main">
	<div
		class="viewer"
		tabindex="0"
		bind:this={viewerElement}
		{onpointerdown}
		{onpointerup}
		{onpointermove}
		{onpointerenter}
		{onpointerleave}
		{onwheel}
		{ondblclick}
		{onkeydown}
		{onkeyup}
		{oncontextmenu}
	></div>

	{#if showInfo}
		<div class="info">
			{#if viewerContext.image.is3D}
				<div>
					<label>
						Lock scroll
						<input type="checkbox" bind:checked={viewerContext.lockScroll} />
					</label>
				</div>
				<div>
					<input
						type="range"
						min="0"
						max={viewerContext.image.depth - 1}
						bind:value={index.value}
					/>
					<span>{index.value}</span>
				</div>
				<WindowLevel />
				<Stretch />
			{/if}
		</div>
	{/if}
</div>

<style>
	div.main {
		display: flex;
		flex: 1;
		position: relative;
		flex-direction: column;
		align-items: center;
	}
	div.info {
		display: flex;
		color: white;
		z-index: 1;
		flex: 0;
		align-items: center;
	}
	div.info span {
		margin: 0.5em;
		width: 3em;
		font-size: small;
		display: inline-block;
	}
	div.viewer {
		position: absolute;
		left: 0;
		top: 0;
		bottom: 0;
		right: 0;
		user-select: none;
		touch-action: none;
		outline: none;
		/* https://stackoverflow.com/questions/59010779/pointer-event-issue-pointercancel-with-pressure-input-pen */
	}
</style>
