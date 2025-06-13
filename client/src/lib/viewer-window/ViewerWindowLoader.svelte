<!--
@component
Used to create the viewerwindow context.

-->
<script lang="ts">
	import { Registration } from '$lib/registration/registration';
	import { Deferred } from '$lib/utils';
	import { WebGL } from '$lib/webgl/webgl';
	import { onMount } from 'svelte';
	import BrowserOverlay from './BrowserOverlay.svelte';
	import ViewerWindow from './ViewerWindow.svelte';
	import { ViewerWindowContext } from './viewerWindowContext.svelte';
	import type { FormAnnotation } from '$lib/datamodel/formAnnotation.svelte';
	import { data } from '$lib/datamodel/model';
	import RegistrationItemLoader from './RegistrationItemLoader.svelte';
	import { getContext } from 'svelte';
    import type { GlobalContext } from '$lib/data-loading/globalContext.svelte';

	interface Props {
		instanceIDs: number[];
	}
	let { instanceIDs }: Props = $props();

	let mainCanvas: HTMLCanvasElement;

	function resizeCanvas() {
		if (mainCanvas) {
			mainCanvas.width = window.innerWidth;
			mainCanvas.height = window.innerHeight;
		}
	}
	const globalContext = getContext<GlobalContext>('globalContext');
	const { creator } = globalContext;

	const { promise, resolve } = new Deferred<ViewerWindowContext>();

	onMount(() => {
		window.addEventListener('resize', resizeCanvas);
		resizeCanvas();

		const webgl = new WebGL(mainCanvas);
		const registration = new Registration();
		const viewerWindowContext = new ViewerWindowContext(webgl, registration, creator, instanceIDs);

		resolve(viewerWindowContext);

		return () => {
			window.removeEventListener('resize', resizeCanvas);
			viewerWindowContext.destroy();
		};
	});

	const filter = (formAnnotation: FormAnnotation) => {
		if (formAnnotation.formSchema.name === 'Pointset registration') return true;
		if (formAnnotation.formSchema.name === 'Affine registration') return true;
        if (formAnnotation.formSchema.name === 'Affine registration') return true;
        if (formAnnotation.formSchema.name === 'RegistrationSet') return true;
		return false;
	};

	const filteredFormAnnotations = data.formAnnotations.filter(filter);
</script>

<canvas bind:this={mainCanvas} class="editor"></canvas>

{#await promise then viewerWindowContext}
	{#each $filteredFormAnnotations as formAnnotation (formAnnotation.id)}
		<RegistrationItemLoader {formAnnotation} registration={viewerWindowContext.registration} />
	{/each}

	<ViewerWindow {viewerWindowContext} />
	{#if viewerWindowContext.browserOverlay}
		<BrowserOverlay {viewerWindowContext} />
	{/if}
{:catch error}
	<div class="error">Failed to initialize viewer: {error.message}</div>
{/await}

<style>
	:global(body) {
		margin: 0;
		height: 100vh;
		font-family: Verdana, sans-serif;
		font-size: small;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}
	canvas {
		position: absolute;
		left: 0;
		top: 0;
		bottom: 0;
		right: 0;
		pointer-events: none;
	}
	.error {
		color: red;
		padding: 1rem;
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		background: rgba(255, 255, 255, 0.9);
		border-radius: 4px;
	}
</style>
