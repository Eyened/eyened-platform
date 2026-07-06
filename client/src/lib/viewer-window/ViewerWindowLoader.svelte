<!--
@component
Used to create the viewerwindow context.

-->
<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { Registration } from "$lib/registration/registration";
    import { Deferred } from "$lib/utils";
    import { WebGL } from "$lib/webgl/webgl";
    import { getContext, onMount } from "svelte";
    import BrowserOverlay from "./BrowserOverlay.svelte";
    import ViewerWindow from "./ViewerWindow.svelte";
    import { ViewerWindowContext } from "./viewerWindowContext.svelte";

    interface Props {
        instanceIDs: string[];
    }
    let { instanceIDs }: Props = $props();

    let mainCanvas: HTMLCanvasElement;

    function resizeCanvas() {
        if (mainCanvas) {
            mainCanvas.width = window.innerWidth;
            mainCanvas.height = window.innerHeight;
        }
    }
    const globalContext = getContext<GlobalContext>("globalContext");
    const { user: creator } = globalContext;

    const { promise, resolve, reject } = new Deferred<ViewerWindowContext>();
    let viewerWindowContext: ViewerWindowContext | null = null;
    let webgl: WebGL | null = null;
    let addedDarkClass = false;

    function handleContextLost(event: Event) {
        event.preventDefault();
        console.error("[WebGL] Context lost - stopping rendering and cleaning up");
        
        if (viewerWindowContext) {
            viewerWindowContext.destroy();
            viewerWindowContext = null;
        }
        
        // Reject the promise so the error UI is shown
        reject(new Error("WebGL context was lost. Please reload the page."));
    }

    function handleContextRestored(event: Event) {
        console.warn("[WebGL] Context restored - this should not happen during normal navigation");
        console.warn("[WebGL] If you see this during navigation, it may indicate a context leak");
        
        // Context restoration is complex - for now, we'll just log it
        // In a production app, you might want to attempt to rebuild the viewer
    }

    onMount(() => {
        
        window.addEventListener("resize", resizeCanvas);
        resizeCanvas();

        if (!document.documentElement.classList.contains('dark')) {
            document.documentElement.classList.add('dark');
            addedDarkClass = true;
        }

        // Add WebGL context event listeners
        mainCanvas.addEventListener("webglcontextlost", handleContextLost);
        mainCanvas.addEventListener("webglcontextrestored", handleContextRestored);

        webgl = new WebGL(mainCanvas);
        const registration = new Registration();
        viewerWindowContext = new ViewerWindowContext(
            webgl,
            registration,
            creator,
            instanceIDs,
        );

        resolve(viewerWindowContext);

        return () => {
            window.removeEventListener("resize", resizeCanvas);
            mainCanvas.removeEventListener("webglcontextlost", handleContextLost);
            mainCanvas.removeEventListener("webglcontextrestored", handleContextRestored);

            if (addedDarkClass) {
                document.documentElement.classList.remove('dark');
                addedDarkClass = false;
            }
            
            if (viewerWindowContext) {
                viewerWindowContext.destroy();
                viewerWindowContext = null;
            }
            
            // Optionally force context loss to ensure cleanup
            try {
                const ext = webgl?.gl.getExtension('WEBGL_lose_context');
                if (ext) {
                    ext.loseContext();
                }
            } catch (error) {
                console.warn("Could not force context loss:", error);
            }
            
            webgl = null;
        };
    });
</script>   

<canvas bind:this={mainCanvas} class="editor" id="mainCanvas"></canvas>

{#await promise then viewerWindowContext}
    <ViewerWindow {viewerWindowContext} />
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
