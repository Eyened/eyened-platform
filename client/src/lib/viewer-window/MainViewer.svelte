<script lang="ts">
    import {
        CLIENT_DEFAULTS,
        mergeClientConfig,
    } from "$lib/config/clientDefaults";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import SliceScrollbar from "$lib/viewer/SliceScrollbar.svelte";
    import ViewControls from "$lib/viewer/ViewControls.svelte";
    import Viewer from "$lib/viewer/Viewer.svelte";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { instances } from "$lib/data/stores.svelte";
    import { resolveEnfaceOverlaySources } from "$lib/registration/resolveEnfaceOverlaySources";
    import { EnfaceProjectionOverlay } from "$lib/viewer/overlays/EnfaceProjectionOverlay";
    import { instanceIdFromImageId } from "./viewerViewState";
    import { getContext, onDestroy, setContext, untrack } from "svelte";
    import { ViewerWindowContext } from "./viewerWindowContext.svelte";

    import { magnifierFeed } from "$lib/workspace/magnifier";
    import { MainViewerContext } from "$lib/viewer/overlays/MainViewerContext.svelte";
    import { FeaturePipetteOverlay } from "./panelSegmentation/FeaturePipetteOverlay";
    import { pointArming } from "$lib/forms/pointArming.svelte";
    import { PointTool } from "$lib/viewer/tools/PointTool.svelte";
    import { MeasureTool } from "$lib/viewer/tools/Measure.svelte";
    import { createViewTool, NoEditCursor } from "$lib/viewer/tools/viewTools";
    import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
    import { formAnnotations, formSchemasByName } from "$lib/data";
    import type { JSONSchema } from "$lib/forms/schemaType";
    import { eyeKey, pointBinding } from "$lib/layers/pointsets";
    import { drawBinding } from "$lib/layers/drawBinding";
    import { bindRegistrationPointTool } from "./panelRegistration/bindRegistrationPointTool";
    import { GridLayers } from "$lib/layers/gridLayers.svelte";
    import { ViewportBlend } from "$lib/layers/viewportBlend.svelte";
    import { LocalizerLines } from "$lib/layers/localizerLines.svelte";
    import { OCTLinesOverlay } from "$lib/viewer/overlays/OCTLinesOverlays";
    import type {
        LayersTarget,
        Workspace,
    } from "$lib/workspace/workspace.svelte";
    interface Props {
        image: AbstractImage;
    }

    let { image }: Props = $props();

    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerWindowContext = getContext<ViewerWindowContext>(
        "viewerWindowContext",
    );

    const viewerContext = new ViewerContext(image, viewerWindowContext);
    setContext("viewerContext", viewerContext);

    const taskContext = getContext<TaskContext | undefined>("taskContext");
    const clientConfig = mergeClientConfig(
        CLIENT_DEFAULTS,
        taskContext?.task.task_definition.config,
    );
    viewerContext.renderControls =
        !clientConfig.layout.hide.includes("Rendering");
    // `layout.hide: ["Registration"]` hides Pointsets and Blend, so P cannot place here.
    const registrationHidden =
        clientConfig.layout.hide.includes("Registration");
    const workspace = getContext<Workspace>("workspace");

    const mainViewerContext = new MainViewerContext(
        viewerContext.instance.id,
        viewerContext.axis,
        viewerWindowContext,
        viewerContext.image,
    );
    setContext("mainViewerContext", mainViewerContext);
    onDestroy(viewerContext.addOverlay(mainViewerContext));
    // This viewport's localizer lines: the B-scan positions of loaded OCTs on this 2D image.
    // The live array, as the strip passed it: a later OCT's positions are pushed into it.
    const localizer = new LocalizerLines(() => {
        // That push notifies nothing, so read the tracked list of loaded sets to see it.
        void viewerWindowContext.photoLocatorSets.length;
        return image.is2D
            ? (viewerWindowContext.photoLocators.get(image.image_id) ?? [])
            : [];
    });
    const gl = image.webgl.gl;
    // This viewport's blend: a swap keeps it; another image or a page turn remounts the viewer and resets it.
    const blend = new ViewportBlend(
        image,
        viewerWindowContext,
        () => workspace.catalogue,
        gl.getParameter(gl.MAX_TEXTURE_IMAGE_UNITS) as number,
        registrationHidden,
    );
    $effect(() => blend.apply(viewerContext));
    onDestroy(() => blend.dispose(viewerContext));
    // Layers' state for this viewport lives here, because Layers remounts its sections when the selection moves.
    const layers: LayersTarget = {
        viewerContext,
        mainViewerContext,
        grids: new GridLayers(viewerContext, viewerWindowContext.registration),
        measure: new MeasureTool(viewerContext.image),
        localizer,
        get projectionSources() {
            return projectionSources;
        },
        get pointTarget() {
            return pointTarget;
        },
        get drawTarget() {
            return drawTarget;
        },
        blend,
    };

    // While mounted, this viewport is a source for its OCT's projection; the newest one wins.
    const position = getContext<(() => number) | undefined>("viewportPosition");

    onDestroy(
        viewerContext.addOverlay(
            magnifierFeed(
                workspace,
                mainViewerContext,
                () => position?.() ?? null,
            ),
        ),
    );
    // The Magnifier never paints from a viewer that is gone.
    onDestroy(() => {
        if (workspace.magnifierSource?.viewerContext === viewerContext)
            workspace.magnifierSource = null;
    });
    if (image.is3D) {
        const enfaceManager = viewerWindowContext.enfaceProjectionManagers.get(
            image.instance.id,
        );
        if (enfaceManager)
            onDestroy(
                enfaceManager.register({
                    mainViewerContext,
                    position: () => position?.() ?? 0,
                }),
            );
    }

    onDestroy(
        viewerContext.addOverlay(
            new FeaturePipetteOverlay(mainViewerContext, globalContext.user.id),
        ),
    );

    // The OCT projections this image shows: its own `_proj`, or linked by registration; in strip order.
    // resolveEnfaceOverlaySources reads registration.revision, so this re-runs when registrations import.
    const projectionSources = $derived.by(() => {
        if (!image.is2D) return [];
        const sources = resolveEnfaceOverlaySources({
            imageId: image.image_id,
            imageWidth: image.width,
            imageHeight: image.height,
            registration: viewerWindowContext.registration,
            managers: viewerWindowContext.enfaceProjectionManagers,
            getImageSize: (id) => {
                for (const [img] of viewerWindowContext.topViewers) {
                    if (img.image_id === id) return [img.width, img.height];
                }
                if (id.endsWith("_proj")) {
                    const mgr =
                        viewerWindowContext.enfaceProjectionManagers.get(
                            id.slice(0, -"_proj".length),
                        );
                    if (mgr) return [mgr.octImage.width, mgr.octImage.depth];
                }
                const meta = instances.get(id);
                return meta ? [meta.columns, meta.rows] : undefined;
            },
            projMode: viewerContext.enfaceProjectionMode,
            linkedModes: viewerContext.enfaceProjectionModesByOct,
        });
        const order = (oct: string) =>
            workspace.catalogue.findIndex(
                (id) => instanceIdFromImageId(id) === oct,
            );
        return sources.sort(
            (a, b) => order(a.octPublicId) - order(b.octPublicId),
        );
    });

    // Paints each projection that is on, from its OCT's newest viewport.
    $effect(() => {
        const sources = projectionSources.flatMap((source) => {
            const from = source.manager.mainViewerContext;
            return source.mode !== "off" && from
                ? [{ ...source, mainViewerContext: from }]
                : [];
        });
        if (!sources.length) return;
        const overlay = new EnfaceProjectionOverlay(sources, image.webgl);
        const remove = viewerContext.addOverlay(overlay);
        return () => {
            remove();
            overlay.destroy();
        };
    });

    $effect(() => {
        const locators = localizer.locators();
        if (!locators.length) return;
        return viewerContext.addOverlay(
            new OCTLinesOverlay(locators, () => localizer.mode),
        );
    });

    // The armed view tool acts in every viewport; strip tiles never take it.
    $effect(() => {
        const tool = createViewTool(workspace.armedTool);
        if (!tool) return;
        const remove = viewerContext.addOverlay(tool);
        return () => {
            remove();
            viewerContext.resetCursor();
        };
    });

    // The eye's current registration: its points show here, and P places them while armed.
    // An armed form point field takes the clicks, so the registration stays read-only then.
    const pointTarget = $derived(
        pointBinding({
            armed: workspace.armedTool === "point" && !pointArming.session,
            hidden: registrationHidden,
            is2D: image.is2D,
            current: viewerWindowContext.pointsets.current(
                eyeKey(image.instance),
            ),
            canEdit: (annotation) => globalContext.canEdit(annotation),
        }),
    );
    const { segmentationContext } = mainViewerContext;
    // Built whatever tool is armed, so the options bar names the target as soon as a Draw tool is picked.
    const drawTarget = $derived(
        drawBinding({
            segmentation: segmentationContext.segmentationItem?.segmentation ?? null,
            activeIndices: segmentationContext.activeIndices,
            toolId: workspace.armedTool,
            canEdit: (segmentation) => globalContext.canEdit(segmentation),
        }),
    );
    // Primitives: a drag rewrites the registration, which must not remount the tool mid-drag.
    const pointId = $derived(pointTarget?.id);
    const pointEditable = $derived(pointTarget?.canEdit ?? false);
    let pointTool = $state.raw<ReturnType<typeof bindRegistrationPointTool>>();
    $effect(() => {
        const id = pointId;
        const canEdit = pointEditable;
        const schema = formSchemasByName.get(
            BUILTIN_VIEWER_FORM_SCHEMA_NAMES.POINTSET_REGISTRATION,
        )?.schema;
        if (id === undefined || !schema) return;
        const binding = untrack(() =>
            bindRegistrationPointTool({
                viewerContext,
                annotationId: id,
                schema: schema as JSONSchema,
                canEdit,
                pointMarker: clientConfig.point_marker,
                onSync: (sync) =>
                    viewerWindowContext.pointsets.sync.set(id, sync),
            }),
        );
        pointTool = binding;
        return () => {
            binding.dispose();
            if (pointTool === binding) pointTool = undefined;
        };
    });
    // Another viewport's edit of this registration reaches this viewport's tool.
    $effect(() => {
        const formData =
            pointId === undefined
                ? undefined
                : formAnnotations.get(pointId)?.form_data;
        const binding = pointTool;
        if (binding) untrack(() => binding.sync(formData));
    });
    // While P is armed, a viewport that cannot take points says so.
    $effect(() => {
        if (workspace.armedTool !== "point" || pointEditable) return;
        const remove = viewerContext.addOverlay(new NoEditCursor());
        return () => {
            remove();
            viewerContext.resetCursor();
        };
    });

    // Reset view and the options bar act on the selected viewport through this handle.
    $effect(() => {
        if (!position) return;
        return workspace.attachViewport(position(), {
            get zoomPercent() {
                return Math.round(viewerContext.transform.scale * 100);
            },
            zoomBy(factor: number) {
                const { width, height } = viewerContext.viewerSize;
                viewerContext.zoom(width / 2, height / 2, factor);
            },
            reset: () => viewerContext.initTransform(),
            layers,
            get titleSuffix() {
                return blend.titleSuffix;
            },
        });
    });

    // Form PointField: mount PointTool while a session is armed. Live SoT is
    // session.fieldValue — do not remount when it changes (only on session key).
    $effect(() => {
        const session = pointArming.session;
        if (!session) return;
        const sessionKey = session.key;
        const { analysis } = session;
        void sessionKey;

        const publicId = () => viewerContext.image.instance.id;

        const tool = new PointTool({
            canEdit: session.canEdit,
            label: session.label ?? "Point",
            pointStyle: session.pointStyle,
            radius: session.radius,
            color: session.color,
            cardinality: analysis.cardinality,
            sparse: analysis.sparse,
            coordinateSpace: analysis.coordinateSpace,
            enumExtras: analysis.enumExtras,
            onChange: (points) => {
                session.setPoints(publicId(), points);
            },
            onPersist: (points) => {
                session.setPoints(publicId(), points);
                session.persist();
            },
        });

        const remove = viewerContext.addOverlay(tool);

        // Keep tool.points in sync with session (PointField edits, other viewers).
        const stopSync = $effect.root(() => {
            $effect(() => {
                tool.points = session.getPoints(publicId());
            });
        });

        return () => {
            stopSync();
            tool.destroy();
            remove();
        };
    });
</script>

<div class="main">
    <!-- ASSUMPTION: the sidebar is removed, not hidden, so the panel header component can be deleted (plan decision 12). -->
    <section
        class="viewer-section"
        class:has-bar={viewerContext.renderControls}
    >
        <Viewer />
        {#if blend.viewportLine}
            <p class="viewport-line text-helper-text-01">
                {blend.viewportLine}
            </p>
        {/if}
        {#if image.is3D && image.depth > 1}
            <SliceScrollbar />
        {/if}
        <ViewControls />
    </section>
</div>

<style>
    /* Base layout styles */
    .main {
        display: flex;
        flex-direction: row;
        flex: 1;
        color: rgba(255, 255, 255, 0.8);
    }

    .viewer-section {
        position: relative;
        display: flex;
        flex: 1;
        min-width: 0;
    }
    /* The bar sits below the image, so it never covers part of the retina. */
    .viewer-section.has-bar {
        padding-bottom: 2rem;
    }
    /* Says why the blend shows only this image; never takes the pointer. */
    .viewport-line {
        position: absolute;
        top: 0.5rem;
        left: 0.5rem;
        z-index: 1;
        pointer-events: none;
        padding: 0.25rem 0.5rem;
        background: var(--color-background);
        color: var(--color-text-primary);
    }
</style>
