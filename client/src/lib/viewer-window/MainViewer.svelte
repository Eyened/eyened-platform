<script lang="ts">
    import {
        CLIENT_DEFAULTS,
        mergeClientConfig,
    } from "$lib/config/clientDefaults";
    import { scaleOf } from "$lib/layers/imageScale";
    import { toHex } from "$lib/utils";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import SliceScrollbar from "$lib/viewer/SliceScrollbar.svelte";
    import ViewControls from "$lib/viewer/ViewControls.svelte";
    import Viewer from "$lib/viewer/Viewer.svelte";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { AbstractImage } from "$lib/webgl/abstractImage";
    import { instances } from "$lib/data/stores.svelte";
    import { resolveEnfaceOverlaySources } from "$lib/registration/resolveEnfaceOverlaySources";
    import { EtdrsCircleOverlay } from "$lib/viewer/overlays/EtdrsCircleOverlay";
    import { EnfaceProjectionOverlay } from "$lib/viewer/overlays/EnfaceProjectionOverlay";
    import { instanceIdFromImageId } from "./viewerViewState";
    import { getContext, onDestroy, setContext, untrack } from "svelte";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
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
    import { bindEtdrsTool } from "./panelETRDS/bindEtdrsTool";
    import { bindDrawTool } from "./panelSegmentation/bindDrawTool";
    import { toolById } from "$lib/workspace/tools/registry";
    import { gridBinding, GridLayers } from "$lib/layers/gridLayers.svelte";
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
    // One fraction for the viewer, so the rings, the circle and the scale agree.
    const grids = new GridLayers(
        viewerContext,
        viewerWindowContext.registration,
        {
            get radiusFraction() {
                return workspace.etdrsFraction;
            },
        },
        mainViewerContext.selection,
    );
    // Layers' state for this viewport lives here, because Layers remounts its sections when the selection moves.
    const distance = workspace.distanceLinesFor(image.image_id);
    const layers: LayersTarget = {
        viewerContext,
        mainViewerContext,
        selection: mainViewerContext.selection,
        grids,
        distance,
        localizer,
        get scale() {
            return scale;
        },
        get projectionSources() {
            return projectionSources;
        },
        get pointTarget() {
            return pointTarget;
        },
        get drawTarget() {
            return drawTarget;
        },
        get etdrsTarget() {
            return etdrsTarget;
        },
        get etdrsTool() {
            return etdrsTool?.tool;
        },
        get pointTool() {
            return pointTool?.tool;
        },
        get formPointTool() {
            return formPointTool;
        },
        blend,
    };

    // One scale per image, shared by Distance and the ETDRS circle.
    const scale = $derived.by(() => {
        // Grid points map through registration, which notifies only through its revision.
        void viewerWindowContext.registration.revision;
        return scaleOf({
            stored: image.resolution,
            grids: grids.scaleGrids(),
            shown: grids.shownKeys(),
            pick: workspace.scalePicks.get(image.image_id),
            fraction: workspace.etdrsFraction,
        });
    });

    // Distance lines always show; the tool draws, moves and deletes them only while Distance is armed.
    onDestroy(
        viewerContext.addOverlay(
            new MeasureTool(
                distance,
                () => scale,
                () => workspace.armedTool === "distance",
                mainViewerContext.selection,
            ),
        ),
    );

    // The ETDRS circle follows the shared pointer in every viewport, each sized with its own image's scale.
    $effect(() => {
        if (workspace.armedTool !== "circle") return;
        return untrack(() =>
            viewerContext.addOverlay(
                new EtdrsCircleOverlay(
                    viewerWindowContext.registration,
                    () => workspace.circleSize,
                    () => scale,
                ),
            ),
        );
    });

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

    const selectedPointset = $derived.by(() => {
        const id = mainViewerContext.selection.pointsetId();
        return id === undefined ? null : (formAnnotations.get(id) ?? null);
    });
    // The eye's registration in use shows here; while P is armed with a pointset selected, P shows and places that one.
    // An armed form point field takes the clicks, so the registration stays read-only then.
    const pointTarget = $derived(
        pointBinding({
            armed: workspace.armedTool === "point" && !pointArming.session,
            hidden: registrationHidden,
            is2D: image.is2D,
            selected: selectedPointset,
            inUse: viewerWindowContext.pointsets.current(
                eyeKey(image.instance),
            ),
            canEdit: (annotation) => globalContext.canEdit(annotation),
        }),
    );
    const { segmentationContext } = mainViewerContext;
    // Built whatever tool is armed, so the options bar names the target as soon as a Draw tool is picked.
    const drawTarget = $derived.by(() => {
        const segmentation =
            segmentationContext.segmentationItem?.segmentation ?? null;
        const color = segmentation
            ? mainViewerContext.assignedFeatureColor(segmentation)
            : undefined;
        return drawBinding({
            segmentation,
            color: color ? toHex(color) : null,
            activeIndices: segmentationContext.activeIndices,
            toolId: workspace.armedTool,
            canEdit: (segmentation) => globalContext.canEdit(segmentation),
        });
    });
    // A primitive, so a new class or a new editable target never rebuilds the tool mid-stroke.
    const drawEditable = $derived(
        drawTarget.reason === null && !segmentationContext.regionToolActive,
    );
    // The armed Draw tool acts in every viewport that can take it; the others show "can't edit".
    $effect(() => {
        const id = workspace.armedTool;
        const editable = drawEditable;
        if (!id || toolById(id).group !== "Draw") return;
        return untrack(() =>
            bindDrawTool({
                toolId: id,
                editable,
                viewerContext,
                segmentationContext,
                workspace,
                report: (message) => (segmentationContext.drawFailed = message),
            }),
        );
    });
    // Primitives: a drag rewrites the registration, which must not remount the tool mid-drag.
    const pointId = $derived(pointTarget.id ?? undefined);
    const pointEditable = $derived(pointTarget.canEdit);
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

    // Built whatever tool is armed, so the options bar names the grid as soon as G is picked.
    const etdrsTarget = $derived(
        gridBinding({
            grid:
                grids.currentId === undefined
                    ? undefined
                    : formAnnotations.get(grids.currentId),
            instanceId: image.instance.id,
            is3D: image.is3D,
            userId: globalContext.user.id,
            canEdit: (grid) => globalContext.canEdit(grid),
        }),
    );
    // A primitive, so a save of the grid never rebuilds the tool mid-drag.
    const etdrsWritable = $derived(
        etdrsTarget.reason === null ? grids.currentId : undefined,
    );
    let etdrsTool = $state.raw<ReturnType<typeof bindEtdrsTool>>();
    // Place ETDRS acts in every viewport that can take it; the others show "can't edit".
    $effect(() => {
        if (workspace.armedTool !== "etdrs") return;
        const id = etdrsWritable;
        return untrack(() => {
            if (id === undefined) {
                const remove = viewerContext.addOverlay(new NoEditCursor());
                return () => {
                    remove();
                    viewerContext.resetCursor();
                };
            }
            const binding = bindEtdrsTool({
                viewerContext,
                gridId: id,
                keepSize: () => workspace.keepGridSize,
            });
            etdrsTool = binding;
            return () => {
                binding.dispose();
                if (etdrsTool === binding) etdrsTool = undefined;
            };
        });
    });
    // The bar's Fovea | Disc edge reaches this viewport's tool.
    $effect(() => {
        const slot = workspace.etdrsSlot;
        if (etdrsTool) etdrsTool.tool.placementIndex = slot;
    });
    // Another viewport's edit of the grid reaches this viewport's tool.
    $effect(() => {
        const formData =
            etdrsWritable === undefined
                ? undefined
                : formAnnotations.get(etdrsWritable)?.form_data;
        const binding = etdrsTool;
        if (binding) untrack(() => binding.sync(formData));
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
            reset: () => {
                viewerContext.initTransform();
                distance.clear();
            },
            layers,
            get titleSuffix() {
                return blend.titleSuffix;
            },
        });
    });

    let formPointTool = $state.raw<PointTool>();
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
        formPointTool = tool;

        // Keep tool.points in sync with session (PointField edits, other viewers).
        const stopSync = $effect.root(() => {
            $effect(() => {
                tool.points = session.getPoints(publicId());
            });
        });

        return () => {
            if (formPointTool === tool) formPointTool = undefined;
            stopSync();
            tool.destroy();
            remove();
        };
    });
    let section: HTMLElement | undefined = $state();
    // Closing the notice unmounts its button; focus goes back to this viewport's image.
    function closeDrawFailed() {
        segmentationContext.drawFailed = null;
        section?.querySelector<HTMLElement>(".viewer")?.focus();
    }
</script>

<div class="main">
    <!-- ASSUMPTION: the sidebar is removed, not hidden, so the panel header component can be deleted (plan decision 12). -->
    <section
        class="viewer-section"
        bind:this={section}
        class:has-bar={viewerContext.renderControls}
    >
        <Viewer />
        {#if blend.viewportLine}
            <p class="viewport-line text-helper-text-01">
                {blend.viewportLine}
            </p>
        {/if}
        {#if segmentationContext.drawFailed}
            <!-- A failed stroke shows where it happened, whichever panel is open. -->
            <div class="draw-failed" class:below-line={!!blend.viewportLine}>
                <InlineNotification
                    title={segmentationContext.drawFailed}
                    subtitle="Try again."
                    onclose={closeDrawFailed}
                />
            </div>
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
    /* Covers the top of the image until closed or until a stroke works. */
    .draw-failed {
        position: absolute;
        top: 0.5rem;
        inset-inline: 0.5rem;
        z-index: 2;
    }
    /* Below the blend line (0.5rem + its 24 px), so it hides neither. */
    .draw-failed.below-line {
        top: 2.5rem;
    }
</style>
