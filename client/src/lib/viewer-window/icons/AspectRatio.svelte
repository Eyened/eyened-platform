<script lang="ts">
	interface Props {
		size?: string;
	}

	let { size = '2em' }: Props = $props();
</script>

<svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 20 20" fill="none">
	<path
		stroke="#ffffff"
		stroke-linecap="round"
		stroke-linejoin="round"
		stroke-width="2"
		d="M10.25 1.75l4 4m-4-4l-4 4m4-4v16.5m0 0l4-4m-4 4l-4-4"
	/>
</svg>
