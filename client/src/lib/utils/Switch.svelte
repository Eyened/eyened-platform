<script lang="ts">
	import { createBubbler } from 'svelte/legacy';

	const bubble = createBubbler();
	interface Props {
		checked?: boolean;
		small?: boolean; //   export let color = "#2196F3";
	}

	let { checked = $bindable(false), small = false }: Props = $props();
	
</script>

<label class="switch" class:small>
	<input type="checkbox" bind:checked onchange={bubble('change')} />
	<span class="slider" class:small></span>
</label>

<style>
	.switch {
		position: relative;
		display: inline-block;
		width: 60px;
		height: 34px;
	}
	.switch.small {
		width: 28px;
		height: 16px;
	}

	.switch input {
		opacity: 0;
		width: 0;
		height: 0;
	}

	.slider {
		position: absolute;
		cursor: pointer;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background-color: #999;
		-webkit-transition: 0.4s;
		transition: 0.4s;
		border-radius: 34px;
	}
	.slider.small {
		border-radius: 16px;
	}

	.slider:before {
		position: absolute;
		content: '';
		height: 26px;
		width: 26px;
		left: 4px;
		bottom: 4px;
		background-color: white;
		-webkit-transition: 0.4s;
		transition: 0.4s;
		border-radius: 50%;
	}
	.slider.small:before {
		height: 11px;
		width: 11px;
		left: 3px;
		bottom: 3px;
	}

	input:checked + .slider {
		background-color: #2196f3;
	}

	input:checked + .slider {
		box-shadow: 0 0 1px #2196f3;
	}

	input:checked + .slider:before {
		-webkit-transform: translateX(26px);
		-ms-transform: translateX(26px);
		transform: translateX(26px);
	}

	input:checked + .slider.small:before {
		-webkit-transform: translateX(12px);
		-ms-transform: translateX(12px);
		transform: translateX(12px);
	}
</style>
