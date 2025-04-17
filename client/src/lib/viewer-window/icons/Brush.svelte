<script lang="ts">
	interface Props {
		size?: string;
	}

	let { size = '2em' }: Props = $props();
</script>

<svg
	height="{size}"
	width="{size}"
	
	version="1.1"
	viewBox="0 0 100 100">

    <path d="M91,48c-14.3,5.5-28.9-5.9-43.2-7.8c-14-1.8-27.8,0.5-41.5,3.7c-6.8,1.6-3.9,12,2.9,10.4C28.1,50,44.6,49.1,63,55.4    c10.9,3.7,19.6,7.3,30.9,3C100.3,55.9,97.5,45.5,91,48z"/>
</svg>


<style>
	svg {
		stroke: currentColor;
		fill: currentColor;
	}
</style>
