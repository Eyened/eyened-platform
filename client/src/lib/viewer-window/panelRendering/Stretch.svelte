<script lang="ts">
	import AspectRatio from '../icons/AspectRatio.svelte';
	import { ViewerContext } from '$lib/viewer/viewerContext.svelte';
	import { getContext } from 'svelte';
	const viewerContext = getContext<ViewerContext>('viewerContext');

	const stretchLog = {
		get value() {
			return Math.log(viewerContext.stretch);
		},
		set value(v) {
			viewerContext.stretch = Math.exp(v);
			viewerContext.initTransform();
		}
	};
</script>

<div id="stretch-container">
	<AspectRatio />
	<div id="controls">
		<input
			type="range"
			bind:value={stretchLog.value}
			min={Math.log(0.3)}
			max={Math.log(20)}
			step="0.1"
		/>
		<div>
			<button onclick={() => (stretchLog.value = Math.log(1))}>1</button>
			<button onclick={() => (stretchLog.value = Math.log(2))}>2</button>
			<button onclick={() => (stretchLog.value = Math.log(4))}>4</button>
			<button onclick={() => (stretchLog.value = Math.log(8))}>8</button>
			<button onclick={() => (stretchLog.value = Math.log(16))}>16</button>
		</div>
	</div>
</div>

<style>
	div#stretch-container {
		display: flex;
		flex-direction: row;
		align-items: center;
	}
	div#controls {
		flex-direction: column;
	}
</style>
