<!--
@component
Creates the viewer window: the WebGL canvas, its ViewerWindowContext and the Workspace.
-->
<script lang="ts">
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { Registration } from "$lib/registration/registration.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import { Deferred } from "$lib/utils";
    import { WebGL } from "$lib/webgl/webgl";
    import {
        CLIENT_DEFAULTS,
        mergeClientConfig,
    } from "$lib/config/clientDefaults";
    import { Workspace } from "$lib/workspace/workspace.svelte";
    import {
        readStripLocalizer,
        readStripTracking,
        readToolMode,
        startStripOn,
    } from "$lib/workspace/workspacePrefs";
    import {
        createWorkspaceUrlWriter,
        parseWorkspaceParams,
    } from "$lib/workspace/workspaceUrl";
    import { getContext, onMount, setContext } from "svelte";
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
    const taskContext = getContext<TaskContext | undefined>("taskContext");

    // Off on a narrow window; else a task takes the strip from its config, /view from the user's choice.
    const strip = startStripOn(
        taskContext
            ? mergeClientConfig(
                  CLIENT_DEFAULTS,
                  taskContext.task.task_definition.config,
              ).layout.strip
            : undefined,
    );

    // One Workspace per viewer window, never a module singleton.
    const urlWriter = createWorkspaceUrlWriter({
        getSearchParams: () => new URLSearchParams(window.location.search),
        replaceUrl: (params) => {
            // Avoid `new URL(...)` (svelte/prefer-svelte-reactivity).
            // Use history.replaceState (not page.url) so we don't fight SvelteKit;
            // readers must use window.location.search (see BrowserOverlay).
            const searchRaw = params.toString();
            const search = searchRaw
                ? `?${searchRaw.replaceAll("%2C", ",")}`
                : "";
            history.replaceState(
                history.state,
                "",
                `${window.location.pathname}${search}${window.location.hash}`,
            );
        },
    });
    const workspace = new Workspace({
        writeUrl: urlWriter.write,
        strip,
        stripTracking: readStripTracking(),
        stripLocalizer: readStripLocalizer(),
        // A task always offers every tool (no switcher); /view starts in the stored mode.
        toolMode: taskContext ? "all" : readToolMode(),
    });
    setContext("workspace", workspace);

    const { promise, resolve, reject } = new Deferred<ViewerWindowContext>();
    let viewerWindowContext: ViewerWindowContext | null = null;
    let webgl: WebGL | null = null;

    function handleContextLost(event: Event) {
        event.preventDefault();
        console.error(
            "[WebGL] Context lost - stopping rendering and cleaning up",
        );

        if (viewerWindowContext) {
            viewerWindowContext.destroy();
            viewerWindowContext = null;
        }

        // Reject the promise so the error UI is shown
        reject(new Error("WebGL context was lost. Please reload the page."));
    }

    function handleContextRestored(_event: Event) {
        console.warn(
            "[WebGL] Context restored - this should not happen during normal navigation",
        );
        console.warn(
            "[WebGL] If you see this during navigation, it may indicate a context leak",
        );

        // Context restoration is complex - for now, we'll just log it
        // In a production app, you might want to attempt to rebuild the viewer
    }

    onMount(() => {
        window.addEventListener("resize", resizeCanvas);
        resizeCanvas();

        // Add WebGL context event listeners
        mainCanvas.addEventListener("webglcontextlost", handleContextLost);
        mainCanvas.addEventListener(
            "webglcontextrestored",
            handleContextRestored,
        );

        webgl = new WebGL(mainCanvas);
        const registration = new Registration();

        viewerWindowContext = new ViewerWindowContext(
            webgl,
            registration,
            creator,
            instanceIDs,
            workspace,
            parseWorkspaceParams(new URLSearchParams(window.location.search)),
        );

        resolve(viewerWindowContext);

        return () => {
            window.removeEventListener("resize", resizeCanvas);
            mainCanvas.removeEventListener(
                "webglcontextlost",
                handleContextLost,
            );
            mainCanvas.removeEventListener(
                "webglcontextrestored",
                handleContextRestored,
            );

            urlWriter.flush();
            if (viewerWindowContext) {
                viewerWindowContext.destroy();
                viewerWindowContext = null;
            }

            // Optionally force context loss to ensure cleanup
            try {
                const ext = webgl?.gl.getExtension("WEBGL_lose_context");
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
