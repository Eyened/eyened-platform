<script lang="ts">
	import type { DialogueType } from '$lib/types';
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';

	const dialogue = getContext<Writable<DialogueType>>('dialogue');

	function isComponent(dialogue: DialogueType) {
		return (
			dialogue !== undefined && typeof dialogue === 'object' && typeof dialogue.query === 'function'
		);
	}
	function props(dialogue: DialogueType) {
		return dialogue?.props ?? {};
	}
</script>

{#if typeof $dialogue === 'string'}
	<div class="overlay">
		<div class="dialogue-container">
			<div class="query">{$dialogue}</div>
			<button class="approve" on:click={() => ($dialogue = undefined)}>Close</button>
		</div>
	</div>
{:else if isComponent($dialogue)}
	<div class="overlay component">
		<div class="dialogue-container">
			<svelte:component this={$dialogue.query} {...props($dialogue)} dialogue={$dialogue} />
		</div>
	</div>
{:else if $dialogue}
	<div class="overlay">
		<div class="dialogue-container">
			<div class="query">{$dialogue.query}</div>
			<div class="buttons">
				<button class="approve" on:click={$dialogue.resolve}>{$dialogue.approve}</button>
				<button class="decline" on:click={$dialogue.reject}>{$dialogue.decline}</button>
			</div>
		</div>
	</div>
{/if}

<style>
	div {
		display: flex;
	}
	.overlay {
		position: fixed;
		top: 0;
		left: 0;
		width: 100vw;
		height: 100vh;
		background-color: rgba(255, 255, 255, 0.8);
		z-index: 9999;
		display: flex;
		justify-content: center;
		align-items: center;
	}
	.overlay.component {
		pointer-events: none;
		background-color: transparent;
	}
	.overlay.component > * {
		pointer-events: auto;
	}
	.dialogue-container {
		/* width: 400px; */
		background-color: #fff;
		border-radius: 4px;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
		padding: 16px;
		flex-direction: column;
	}
	div.buttons {
		flex: 1;
		justify-content: center;
	}
	button {
		margin: 0.2em;
	}
	.query {
		font-size: 20px;
		margin-bottom: 16px;
	}

	.approve,
	.decline {
		margin-top: 16px;
		padding: 8px 16px;
		border-radius: 1px;
		cursor: pointer;
	}
	.approve:hover,
	.decline:hover {
		background-color: aliceblue;
	}
</style>
