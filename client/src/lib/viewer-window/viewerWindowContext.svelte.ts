import { ImageLoader, type LoadedImages } from "$lib/data-loading/imageLoader";
import {
    fetchInstance,
    fetchFormAnnotations,
    fetchPatient,
} from "$lib/data/api";
import { instances } from "$lib/data/stores.svelte";
import {
    loadPhotoLocators,
    type PhotoLocator,
} from "$lib/registration/photoLocators";
import type { Registration } from "$lib/registration/registration.svelte";
import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import { AbstractImage } from "$lib/webgl/abstractImage";
import type { Image3D } from "$lib/webgl/image3D";
import type { WebGL } from "$lib/webgl/webgl";
import { catalogueEntry } from "$lib/workspace/imageMeta";
import type { Workspace } from "$lib/workspace/workspace.svelte";
import type { CatalogueEntry } from "$lib/workspace/workspaceRules";
import type { WorkspaceUrlState } from "$lib/workspace/workspaceUrl";
import { SvelteMap, SvelteSet } from "svelte/reactivity";
import type { ImageGET } from "../../types/openapi_types";
import { EnfaceProjectionManager } from "./enfaceProjectionManager.svelte";
import type {
    RegistrationEditorSession,
    SeriesBlendSession,
} from "./panelRegistration/registrationSession";

/** What a ViewerContext reads from the workspace: the remembered slice, Lock and strip tracking. */
export type WorkspaceView = Pick<
    Workspace,
    "peekIndex" | "recordIndex" | "isLocked" | "setLocked" | "stripTracking"
>;

export class ViewerWindowContext {
    private imagesIndex = new Map<string, Promise<LoadedImages>>();
    private bySOPInstanceUID = new Map<string, LoadedImages>();

    private viewers = new Set<ViewerContext>();
    /** Paint these instead of `viewers` while the editor or series blend is open. */
    private foregroundViewers = new SvelteSet<ViewerContext>();

    public registrationEditor: RegistrationEditorSession | null = $state(null);
    public seriesBlend: SeriesBlendSession | null = $state(null);

    public instanceIds: string[] = $state([]);

    public readonly imageLoader: ImageLoader;
    public readonly topViewers = new SvelteMap<AbstractImage, ViewerContext>();
    /** Loaded images by image id. */
    public readonly images = new SvelteMap<string, AbstractImage>();
    public readonly enfaceProjectionManagers = new SvelteMap<
        string,
        EnfaceProjectionManager
    >();

    photoLocators = new SvelteMap<string, PhotoLocator[]>();
    photoLocatorSets: PhotoLocator[][] = $state([]);

    public readonly viewState: WorkspaceView;

    private frame: number = 0;
    private loadedPatientIds = new Set<number>();
    private destroyed = false;
    private hydrated = false;

    constructor(
        public readonly webgl: WebGL,
        public readonly registration: Registration,
        public readonly creator: unknown,
        instanceIDs: string[],
        private readonly workspace: Workspace,
        private readonly initialUrl: WorkspaceUrlState,
    ) {
        this.imageLoader = new ImageLoader(webgl);
        this.viewState = workspace;

        // start rendering loop
        const loop = () => {
            this.frame = requestAnimationFrame(loop);
            this.repaint();
        };
        loop();

        void this.setInstanceIDs(instanceIDs)
            .then((entries) => this.hydrate(entries))
            .catch((error) => {
                console.error(
                    "[workspace] initial load failed; opening what loaded",
                    error,
                );
                this.hydrate(
                    [...this.images.values()].map((image) =>
                        catalogueEntry(image.image_id, image.instance),
                    ),
                );
            });
    }

    addViewer(viewer: ViewerContext, foreground = false) {
        const viewers = foreground ? this.foregroundViewers : this.viewers;
        viewers.add(viewer);
        return () => {
            viewers.delete(viewer);
        };
    }

    openRegistrationEditor(session: RegistrationEditorSession) {
        this.seriesBlend = null;
        this.registrationEditor = session;
    }

    closeRegistrationEditor() {
        this.registrationEditor = null;
    }

    openSeriesBlend(session: SeriesBlendSession) {
        this.registrationEditor = null;
        this.seriesBlend = session;
    }

    closeSeriesBlend() {
        this.seriesBlend = null;
    }

    removeViewer(viewer: ViewerContext) {
        this.viewers.delete(viewer);
        this.foregroundViewers.delete(viewer);
    }

    repaint() {
        this.webgl.clear({
            left: 0,
            bottom: 0,
            width: this.webgl.canvas.width,
            height: this.webgl.canvas.height,
        });
        const paint =
            this.registrationEditor || this.seriesBlend
                ? this.foregroundViewers
                : this.viewers;
        for (const viewer of paint) viewer.repaint();
    }

    private hydrate(entries: CatalogueEntry[]) {
        if (this.destroyed) return;
        this.hydrated = true;
        this.workspace.hydrate(entries, this.initialUrl);
    }

    /** Loads the instances and returns their catalogue entries, in opened order. */
    async setInstanceIDs(ids: string[]): Promise<CatalogueEntry[]> {
        this.workspace.prune(ids);

        // ensure metadata of all instances is loaded
        const fetchOptions = {
            with_segmentations: true,
            with_form_annotations: true,
            with_model_segmentations: true,
        };
        const idsNeedingFetch = ids.filter((id) => {
            const inst = instances.get(id);
            // Search-ingested instances lack embedded segmentations / form annotations
            return !inst || !("segmentations" in inst);
        });
        if (idsNeedingFetch.length) {
            await Promise.all(
                idsNeedingFetch.map((id) => fetchInstance(id, fetchOptions)),
            );
            // Data is automatically ingested into global stores by fetchInstance
        }

        this.instanceIds = ids;

        // Fetch all form annotations for the involved patient(s)
        const patientIds = Array.from(
            new Set(
                ids
                    .map((id) => instances.get(id)?.patient?.id)
                    .filter((pid): pid is number => typeof pid === "number"),
            ),
        );
        if (patientIds.length) {
            await Promise.all(
                patientIds
                    .filter((pid) => !this.loadedPatientIds.has(pid))
                    .map(async (pid) => {
                        await fetchFormAnnotations({ patient_id: pid });
                        await fetchPatient(pid, {
                            include_attributes: true,
                        });
                        this.loadedPatientIds.add(pid);
                    }),
            );
        }

        // Load images for all instances
        const loadIds: string[] = [];
        const loadPromises: Promise<LoadedImages>[] = [];
        for (const id of ids) {
            const instance = instances.get(id);
            if (instance) {
                loadIds.push(id);
                loadPromises.push(this.loadImage(instance));
            } else console.warn(`Instance with id ${id} not found after fetch`);
        }
        const entries: CatalogueEntry[] = [];
        const results = await Promise.allSettled(loadPromises);
        results.forEach((result, i) => {
            if (result.status === "rejected") {
                console.error(`Loading instance ${loadIds[i]} failed`);
                return;
            }
            for (const image of result.value) {
                entries.push(catalogueEntry(image.image_id, image.instance));
            }
        });
        if (this.hydrated) this.workspace.addImages(entries);
        return entries;
    }

    destroy() {
        this.destroyed = true;
        // Cancel animation frame
        cancelAnimationFrame(this.frame);

        // Dispose all images and their resources
        for (const [image] of this.topViewers.entries()) {
            try {
                image.dispose();
            } catch (error) {
                console.error(
                    `Error disposing image ${image.image_id}:`,
                    error,
                );
            }
        }

        // Clear all maps and sets
        this.topViewers.clear();
        this.images.clear();
        this.viewers.clear();
        this.foregroundViewers.clear();
        this.imagesIndex.clear();
        this.bySOPInstanceUID.clear();
        this.photoLocators.clear();
        this.photoLocatorSets = [];
        this.instanceIds = [];
        for (const manager of this.enfaceProjectionManagers.values()) {
            manager.dispose();
        }
        this.enfaceProjectionManagers.clear();
    }

    async loadImage(instance: ImageGET): Promise<LoadedImages> {
        // Start loading if not already in progress
        if (!this.imagesIndex.has(instance.id)) {
            const loadPromise = this.imageLoader
                .load(instance)
                .then((loadedImages) => {
                    // Process images once loaded
                    for (const image of loadedImages) {
                        this.importPhotoLocators(image);
                    }

                    // Set up indices
                    this.bySOPInstanceUID.set(
                        instance.sop_instance_uid,
                        loadedImages,
                    );

                    // Create viewer contexts
                    for (const image of loadedImages) {
                        const viewerContext = new ViewerContext(image, this);
                        // Strip tiles show the middle slice; only the main viewer scrolls.
                        viewerContext.lockScroll = true;
                        if (image.image_id.endsWith("_proj")) {
                            viewerContext.enfaceProjectionMode = "binary";
                        }
                        this.topViewers.set(image, viewerContext);
                        this.images.set(image.image_id, image);
                    }

                    const projImage = loadedImages.find((img) =>
                        img.image_id.endsWith("_proj"),
                    );
                    const octImage = loadedImages.find((img) => img.is3D);
                    if (projImage?.is2D && octImage?.is3D) {
                        this.enfaceProjectionManagers.set(
                            instance.id,
                            new EnfaceProjectionManager(octImage as Image3D),
                        );
                    }

                    return loadedImages;
                });

            this.imagesIndex.set(instance.id, loadPromise);
        }

        // Return cached promise (either existing or newly created)
        return this.imagesIndex.get(instance.id)!;
    }
    importPhotoLocators(image: AbstractImage) {
        const photoLocators = loadPhotoLocators(image);
        this.photoLocatorSets.push(photoLocators);

        for (const locator of photoLocators) {
            for (const key of ["enfaceImageId", "octImageId"]) {
                const image_id = String(locator[key as keyof PhotoLocator]);
                if (!this.photoLocators.has(image_id)) {
                    this.photoLocators.set(image_id, []);
                }
                this.photoLocators.get(image_id)!.push(locator);
            }
        }
        const locators = this.photoLocators.get(image.image_id) ?? [];
        this.registration.addImage(image, locators);
    }

    getImages(instanceID: string): Promise<LoadedImages> {
        const instance = instances.get(instanceID);
        if (instance === undefined) {
            throw new Error(`Instance with id ${instanceID} not found`);
        }
        return this.loadImage(instance);
    }
}
