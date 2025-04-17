<script lang="ts">
	interface Props {
		size?: string;
	}

	let { size = '2em' }: Props = $props();
</script>

<svg
	xmlns="http://www.w3.org/2000/svg"
	height={size}
	width={size}
	viewBox="0 0 32 32"
>
	<path d="M21.66,6.1,8.93,18.83a1,1,0,0,0,0,1.41l2.83,2.83a1,1,0,0,0,1.41,0L16,20.24l9.9-9.9a1,1,0,0,0,.24-.39l1.41-4.24a1,1,0,0,0-.24-1,16,16,0,1,0,0,22.63L25.9,25.9A14,14,0,1,1,24.64,5L22,5.86A1,1,0,0,0,21.66,6.1ZM25,7,24.32,9.1l-9,9-1.41-1.41,9-9Z"/>
</svg>

<style>
	svg {
		stroke: none;
		fill: currentColor;
	}
</style>
