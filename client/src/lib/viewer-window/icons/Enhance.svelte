<script lang="ts">
	interface Props {
		size?: string;
	}

	let { size = '2em' }: Props = $props();
</script>

<svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 64 64">
	<path
		d="M24.67,48.7c6.07-.85,9.19-8.07,5.27-12.79-.18-.21-.37-.42-.57-.62a9,9,0,0,0-1.93-1.48c-4.71-2.67-10.65.44-11.57,5.78-.76,4.4-1.82,10.59-1.82,10.59Z"
	/>
	<path
		d="M60.44,4.09h0a3.18,3.18,0,0,1,.19,4.28L39.19,33.94a3.18,3.18,0,0,1-4.68.21L30.38,30a3.17,3.17,0,0,1,.2-4.67L56.15,3.9A3.17,3.17,0,0,1,60.44,4.09Z"
	/>
	<path
		d="M35.75,40.19c15.22.56,27,4.51,27,9.28,0,5.17-13.79,9.36-30.79,9.36S1.17,54.64,1.17,49.47c0-2.75,3.9-5.22,10.11-6.93"
	/>
	<path
		d="M39.82,44c7.69.72,13.27,2.9,13.27,5.48,0,3.17-8.46,5.74-18.89,5.74-6.41,0-12.08-1-15.49-2.46"
	/>
	<path d="M34.84,28.84l-.94-.91A1.1,1.1,0,0,1,34,26.28L38,23" />
</svg>

<style>
	svg {
		stroke: currentColor;
		fill: none;
        stroke-width: 4;
	}
</style>
