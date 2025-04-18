<script lang="ts">
	import { onMount } from 'svelte';

	interface Props {
		start?: number;
		end?: number;
	}

	let { start = $bindable(0), end = $bindable(1) }: Props = $props();

	let leftHandle: HTMLDivElement = $state();
	let body: HTMLDivElement = $state();
	let slider: HTMLDivElement = $state();
	let windowHandle: Window;
	onMount(() => {
		windowHandle = slider.ownerDocument.defaultView!;
	});

	function clamp(x, lower, upper) {
		return Math.max(Math.min(x, upper), lower);
	}
	function draggable(node) {
		let x: number;
		let y: number;
		function handleMousedown(event) {
			if (event.type === 'touchstart') {
				event = event.touches[0];
			}
			x = event.clientX;
			y = event.clientY;
			node.dispatchEvent(
				new CustomEvent('dragstart', {
					detail: { x, y }
				})
			);
			windowHandle.addEventListener('mousemove', handleMousemove);
			windowHandle.addEventListener('mouseup', handleMouseup);
			windowHandle.addEventListener('touchmove', handleMousemove);
			windowHandle.addEventListener('touchend', handleMouseup);
		}
		function handleMousemove(event) {
			if (event.type === 'touchmove') {
				event = event.changedTouches[0];
			}
			const dx = event.clientX - x;
			const dy = event.clientY - y;
			x = event.clientX;
			y = event.clientY;
			node.dispatchEvent(
				new CustomEvent('dragmove', {
					detail: { x, y, dx, dy }
				})
			);
		}
		function handleMouseup(event) {
			x = event.clientX;
			y = event.clientY;
			node.dispatchEvent(
				new CustomEvent('dragend', {
					detail: { x, y }
				})
			);
			windowHandle.removeEventListener('mousemove', handleMousemove);
			windowHandle.removeEventListener('mouseup', handleMouseup);
			windowHandle.removeEventListener('touchmove', handleMousemove);
			windowHandle.removeEventListener('touchend', handleMouseup);
		}
		node.addEventListener('mousedown', handleMousedown);
		node.addEventListener('touchstart', handleMousedown);
		return {
			destroy() {
				node.removeEventListener('mousedown', handleMousedown);
				node.removeEventListener('touchstart', handleMousedown);
			}
		};
	}
	function setHandlePosition(which) {
		return function (evt) {
			const { left, right } = slider.getBoundingClientRect();
			const parentWidth = right - left;
			const p = Math.min(Math.max((evt.detail.x - left) / parentWidth, 0), 1);
			if (which === 'start') {
				start = p;
				end = Math.max(end, p);
			} else {
				start = Math.min(p, start);
				end = p;
			}
		};
	}
	function setHandlesFromBody(evt) {
		const { width } = body.getBoundingClientRect();
		const { left, right } = slider.getBoundingClientRect();
		const parentWidth = right - left;
		const leftHandleLeft = leftHandle.getBoundingClientRect().left;
		const pxStart = clamp(leftHandleLeft + evt.detail.dx - left, 0, parentWidth - width);
		const pxEnd = clamp(pxStart + width, width, parentWidth);
		const pStart = pxStart / parentWidth;
		const pEnd = pxEnd / parentWidth;
		start = pStart;
		end = pEnd;
	}

	// Handler function to replace the legacy preventDefault and stopPropagation
	function handleDragMove(handlerFn) {
		return (event) => {
			event.preventDefault();
			event.stopPropagation();
			handlerFn(event);
		};
	}
</script>

<div class="double-range-container">
	<div class="slider" bind:this={slider}>
		<div
			class="body"
			bind:this={body}
			use:draggable
			on:dragmove={handleDragMove(setHandlesFromBody)}
			style="
				left: {100 * start}%;
				right: {100 * (1 - end)}%;
			"
		></div>
		<div
			class="handle"
			bind:this={leftHandle}
			data-which="start"
			use:draggable
			on:dragmove={handleDragMove(setHandlePosition('start'))}
			style="
				left: {100 * start}%
			"
		></div>
		<div
			class="handle"
			data-which="end"
			use:draggable
			on:dragmove={handleDragMove(setHandlePosition('end'))}
			style="
				left: {100 * end}%
			"
		></div>
	</div>
</div>

<style>
	.double-range-container {
		width: 100%;
		height: 20px;
		user-select: none;
		box-sizing: border-box;
		white-space: nowrap;
	}
	.slider {
		position: relative;
		width: 100%;
		height: 6px;
		top: 50%;
		transform: translate(0, -50%);
		background-color: #e2e2e2;
		box-shadow:
			inset 0 7px 10px -5px #4a4a4a,
			inset 0 -1px 0px 0px #9c9c9c;
		border-radius: 1px;
	}
	.handle {
		cursor: pointer;
		position: absolute;
		top: 50%;
		width: 0;
		height: 0;
	}
	.handle:after {
		content: ' ';
		box-sizing: border-box;
		position: absolute;
		border-radius: 50%;
		width: 16px;
		height: 16px;
		background-color: rgba(255, 255, 255, 0.5);
		border: 1px solid #c7c7c7;
		transform: translate(-50%, -50%);
	}
	.handle:hover::after {
		background-color: rgba(255, 255, 255, 0.9);
	}
	.body {
		cursor: pointer;
		top: 0;
		position: absolute;
		background-color: #34a1ff;
		bottom: 0;
	}
</style>
