<script lang="ts">
	import { onMount, type Snippet } from 'svelte';

	interface Props {
		active?: boolean;
		disabled?: boolean;
		tooltip?: string | undefined;
		isText?: boolean;
		children?: Snippet;
		onclick?: () => void;
	}

	let {
		active = false,
		disabled = false,
		tooltip = undefined,
		isText = false,
		children,
		onclick = () => {}
	}: Props = $props();

	let tooltipElem: HTMLElement = $state();
	let tooltiptextElem: HTMLElement = $state();

	onMount(() => {
		if (!tooltiptextElem || !tooltipElem) return;
		const adjustTooltipPosition = () => {
			const rect = tooltipElem.getBoundingClientRect();
			const textRect = tooltiptextElem.getBoundingClientRect();
			if (rect.left + textRect.width > window.innerWidth) {
				tooltiptextElem.style.right = '0';
			} else {
				tooltiptextElem.style.right = 'auto';
			}
		};

		tooltipElem.addEventListener('mouseover', adjustTooltipPosition);
		tooltipElem.addEventListener('mouseout', () => (tooltiptextElem.style.right = 'auto'));
	});
	function click() {
		if (disabled) return;
		onclick();
	}
</script>

<div class="tooltip" bind:this={tooltipElem}>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<span class="icon" class:isText class:active class:disabled onclick={click}>
		{@render children?.()}
	</span>
	{#if tooltip}
		<span class="tooltiptext" bind:this={tooltiptextElem}>{tooltip}</span>
	{/if}
</div>

<style>
	span.icon {
		display: flex;
		align-items: center;
		cursor: pointer;
		width: 1.5em;
		height: 1.5em;
		color: rgba(255, 255, 255, 0.6);
		margin: 0.2em;
		padding: 0.2em;
		border-radius: 50%;
		transition: all 0.3s ease;
	}
	span.icon.isText {
		width: auto;
	}
	span.icon:hover {
		border-radius: 2px;
		color: rgba(255, 255, 255, 0.8);
		background-color: rgba(100, 255, 255, 0.3);
	}
	span.icon.active {
		border-radius: 2px;
		color: rgba(255, 255, 255, 1);
		background-color: rgba(255, 255, 255, 0.4);
	}
	span.icon.disabled {
		cursor: not-allowed;
		border-radius: 2px;
		color: rgba(255, 255, 255, 0.1);
		background-color: rgba(255, 255, 255, 0);
	}

	.tooltip {
		position: relative;
		display: inline-block;
	}
	.tooltiptext {
		pointer-events: none;
	}
	.tooltip .tooltiptext {
		background-color: #555;
		opacity: 0;
		visibility: hidden;
		color: #fff;
		text-align: center;
		border-radius: 2px;
		padding: 0.2em 1em;
		position: absolute;
		z-index: 10;
		transition: opacity 0.3s ease;
		transition-delay: 0.5s;
	}

	.tooltip:hover .tooltiptext {
		visibility: visible;
		opacity: 1;
	}
</style>
