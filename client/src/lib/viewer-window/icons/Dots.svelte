<script lang="ts">
	interface Props {
		size?: string;
	}

	let { size = '3em' }: Props = $props();
</script>

<svg
	xmlns="http://www.w3.org/2000/svg"
	width={size}
	height={size}
	viewBox="0 0 256 256"
	id="Flat"
>
	<path
		d="M128,28A100,100,0,1,0,228,128,100.11332,100.11332,0,0,0,128,28Zm0,192a92,92,0,1,1,92-92A92.10416,92.10416,0,0,1,128,220Zm8-92a8,8,0,1,1-8-8A8.00917,8.00917,0,0,1,136,128Zm48,0a8,8,0,1,1-8-8A8.00917,8.00917,0,0,1,184,128Zm-96,0a8,8,0,1,1-8-8A8.00917,8.00917,0,0,1,88,128Z"
	/>
</svg>

<style>
	svg {
		fill: currentColor;
		stroke: none;
	}
</style>
