<script lang="ts">
	import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import { getContext } from 'svelte';
	import WindowLevel from './WindowLevel.svelte';
	import Stretch from './Stretch.svelte';

	let { radio = true } = $props();
	const viewerContext = getContext<ViewerContext>('viewerContext');

	const options = {
		Original: 'O<u>r</u>iginal',
		'Contrast enhanced': 'Contrast <u>e</u>nhanced',
		'Color balanced': 'Color <u>b</u>alanced',
		CLAHE: 'CLA<u>H</u>E',
		Sharpened: '<u>S</u>harpened',
		'Histogram matched': 'Histogram <u>m</u>atched',
		Luminance: '<u>L</u>uminance'
	};
</script>

<div class="main">
	<div class="section">
		<WindowLevel />
	</div>
	{#if viewerContext.image.is2D}
		<div>
			{#if radio}
				<ul>
					{#each Object.entries(options) as [option, label]}
						<li>
							<label>
								<input type="radio" bind:group={viewerContext.renderMode} value={option} />
								{@html label}
							</label>
						</li>
					{/each}
				</ul>
			{:else}
				<select bind:value={viewerContext.renderMode}>
					{#each Object.entries(options) as [option, label]}
						<option value={option}>
							{option}
						</option>
					{/each}
				</select>
			{/if}
		</div>
	{/if}
	<!-- <div class="section linking">
		<LinkImages />
		<div class="link-settings">
			{#if image.is3D}
				<label>
					<span>Lock scroll:</span>
					<input type="checkbox" bind:checked={viewerContext.lockScroll} />
				</label>
			{/if}
		</div>
	</div> -->
	{#if viewerContext.image.is3D}
		<div class="section">
			<Stretch />
		</div>
	{/if}
</div>

<style>
	label {
		white-space: nowrap;
	}
	div {
		display: flex;
	}
	div.main {
		padding: 0.5em;
	}
	div.main {
		flex-direction: column;
	}
	div.section {
		margin-top: 1em;
		padding-top: 1em;
		border-top: 1px solid rgba(255, 255, 255, 0.2);
	}

	ul {
		list-style-type: none;
		padding: 0;
	}
	label:hover {
		color: white;
	}
</style>
