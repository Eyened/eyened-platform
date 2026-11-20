<!--
@component
Creates the viewer window: the WebGL canvas, its ViewerWindowContext and the Workspace.
Without WebGL 2, or once the browser drops the context, a notice takes the window's place.
-->
<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { Registration } from "$lib/registration/registration.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import { WebGL } from "$lib/webgl/webgl";
    import {
        CLIENT_DEFAULTS,
        mergeClientConfig,
    } from "$lib/config/clientDefaults";
    import { Workspace } from "$lib/workspace/workspace.svelte";
    import {
        readMagnifier,
        readPaint,
        readStripTracking,
        readToolMode,
        startStripOn,
    } from "$lib/workspace/workspacePrefs";
    import {
        createWorkspaceUrlWriter,
        parseWorkspaceParams,
    } from "$lib/workspace/workspaceUrl";
    import { flushSync, getContext, onMount, setContext } from "svelte";
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
        magnifier: readMagnifier(),
        paint: readPaint(),
        // A task always offers every tool (no switcher); /view starts in the stored mode.
        toolMode: taskContext ? "all" : readToolMode(),
    });
    setContext("workspace", workspace);

    let viewerWindowContext = $state<ViewerWindowContext | null>(null);
    let failure = $state<"no-webgl" | "lost" | null>(null);
    let webgl: WebGL | null = null;
    let reload = $state<HTMLElement | null>(null);

    function handleContextLost(event: Event) {
        event.preventDefault();
        console.error(
            "[WebGL] Context lost - stopping rendering and cleaning up",
        );
        // The window unmounts before its context is destroyed under it.
        failure = "lost";
        flushSync();
        // Reload is the only way on, so it takes focus.
        reload?.focus();
        viewerWindowContext?.destroy();
        viewerWindowContext = null;
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
        resizeCanvas();
        // Before any listener, so a failure leaves nothing behind.
        try {
            webgl = new WebGL(mainCanvas);
        } catch (error) {
            console.error(error);
            failure = "no-webgl";
            return;
        }
        window.addEventListener("resize", resizeCanvas);
        mainCanvas.addEventListener("webglcontextlost", handleContextLost);
        mainCanvas.addEventListener(
            "webglcontextrestored",
            handleContextRestored,
        );

        viewerWindowContext = new ViewerWindowContext(
            webgl,
            new Registration(),
            creator,
            instanceIDs,
            workspace,
            parseWorkspaceParams(new URLSearchParams(window.location.search)),
        );

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

{#if failure}
    <!-- relative: the absolute canvas would otherwise paint over it. -->
    <div
        class="relative flex h-full items-center-safe justify-center overflow-y-auto p-4"
    >
        <div
            class="flex max-w-112 min-w-0 flex-col items-start gap-4 break-words"
        >
            {#if failure === "lost"}
                <InlineNotification
                    title="The viewer stopped"
                    subtitle="The browser's graphics (WebGL) context was lost. Reload the page to continue."
                />
                <Button
                    variant="secondary"
                    bind:ref={reload}
                    onclick={() => location.reload()}>Reload page</Button
                >
            {:else}
                <InlineNotification
                    title="The viewer can't start"
                    subtitle="WebGL 2 isn't available. Turn on hardware acceleration or try another browser."
                />
            {/if}
        </div>
    </div>
{:else if viewerWindowContext}
    <ViewerWindow {viewerWindowContext} />
{/if}

<style>
    canvas {
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        right: 0;
        pointer-events: none;
    }
</style>
