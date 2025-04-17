<script lang="ts">
	let { annotation, scanNr, area } = $props();
</script>

<li>
	<div class="annotation-info">
		<span class="annotation-id">[{annotation.id}]</span>
		<span class="feature-name">{annotation.feature.name}</span>
	</div>

	<div class="area">
		{#if area !== undefined}
			{#if area < 0.01}
				{(area * 1e6).toFixed(0)} μm²
			{:else}
				{area.toFixed(4)} mm²
			{/if}
		{/if}
	</div>
</li>

<style>
	div {
		display: flex;
	}
	div.annotation-info {
		flex-direction: column;
		flex: 2;
	}
	li {
		display: flex;
		flex: 1;
		flex-direction: row;
		margin-bottom: 0.1em;
		padding: 0.2em;
		/* border: 1px solid rgba(255, 255, 255, 0.1); */
	}

	li:nth-child(even) {
		background-color: rgba(255, 255, 255, 0.1);
	}
	li:nth-child(odd) {
		background-color: rgba(255, 255, 255, 0.05);
	}
	li:hover {
		background-color: rgba(255, 255, 255, 0.1);
	}
	.annotation-id {
		font-size: x-small;
		color: rgba(255, 255, 255, 0.5);
	}
	.feature-name,
	.creator-name {
		flex: 1;
	}
	.area {
		flex: 1;
		align-items: right;
	}
</style>
