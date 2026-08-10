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
import type { Registration } from "$lib/registration/registration";
import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import { AbstractImage } from "$lib/webgl/abstractImage";
import type { Image3D } from "$lib/webgl/image3D";
import type { WebGL } from "$lib/webgl/webgl";
import { SvelteMap } from "svelte/reactivity";
import type { ImageGET } from "../../types/openapi_types";
import MainViewer from "./MainViewer.svelte";
import { EnfaceProjectionManager } from "./enfaceProjectionManager.svelte";
import type { ViewerViewStateController } from "./viewerViewState";
import { instanceIdFromImageId } from "./viewerViewState";

export type MainPanelType = {
    component: any;
    props: any;
};

export class ViewerWindowContext {
    private imagesIndex = new Map<string, Promise<LoadedImages>>();
    private bySOPInstanceUID = new Map<string, LoadedImages>();

    private viewers = new Set<ViewerContext>();

    public instanceIds: string[] = $state([]);

    public mainPanels: MainPanelType[] = $state([]);

    public readonly imageLoader: ImageLoader;
    public readonly topViewers = new SvelteMap<AbstractImage, ViewerContext>();
    public readonly enfaceProjectionManagers = new SvelteMap<
        string,
        EnfaceProjectionManager
    >();

    photoLocators = new SvelteMap<string, PhotoLocator[]>();
    photoLocatorSets: PhotoLocator[][] = $state([]);

    public readonly viewState: ViewerViewStateController | undefined;

    private frame: number = 0;
    private loadedPatientIds = new Set<number>();

    constructor(
        public readonly webgl: WebGL,
        public readonly registration: Registration,
        public readonly creator: unknown,
        instanceIDs: string[] = [],
        viewState?: ViewerViewStateController,
    ) {
        this.imageLoader = new ImageLoader(webgl);
        this.viewState = viewState;

        // start rendering loop
        const loop = () => {
            this.frame = requestAnimationFrame(loop);
            this.repaint();
        };
        loop();

        void this.setInstanceIDs(instanceIDs)
            .then(async () => {
                await this.restoreMainViewersFromViewState();
                this.viewState?.enableRecording();
            })
            .catch(async (error) => {
                console.error(
                    "[viewerViewState] initial load failed; restoring/enabling anyway",
                    error,
                );
                try {
                    await this.restoreMainViewersFromViewState();
                } catch (restoreError) {
                    console.error(
                        "[viewerViewState] failed to restore open viewers",
                        restoreError,
                    );
                }
                this.viewState?.enableRecording();
            });
    }

    addViewer(viewer: ViewerContext) {
        this.viewers.add(viewer);
        return () => this.viewers.delete(viewer);
    }

    removeViewer(viewer: ViewerContext) {
        this.viewers.delete(viewer);
    }

    repaint() {
        this.webgl.clear({
            left: 0,
            bottom: 0,
            width: this.webgl.canvas.width,
            height: this.webgl.canvas.height,
        });
        this.viewers.forEach((viewer) => viewer.repaint());
    }

    async setInstanceIDs(ids: string[]) {
        this.viewState?.prune(ids);

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
        const loadPromises: Promise<unknown>[] = [];
        for (const id of ids) {
            const instance = instances.get(id);
            if (instance) loadPromises.push(this.loadImage(instance));
            else console.warn(`Instance with id ${id} not found after fetch`);
        }
        await Promise.all(loadPromises);
    }

    destroy() {
        this.viewState?.flush();
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
        this.viewers.clear();
        this.imagesIndex.clear();
        this.bySOPInstanceUID.clear();
        this.photoLocators.clear();
        this.photoLocatorSets = [];
        this.mainPanels = [];
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
                        if (image.image_id.endsWith("_proj")) {
                            viewerContext.enfaceProjectionMode = "binary";
                        }
                        this.topViewers.set(image, viewerContext);
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

    addImagePanel(image: AbstractImage) {
        this.mainPanels.push({ component: MainViewer, props: { image } });
        this.syncMainPanelsToViewState();
    }

    setImagePanel(image: AbstractImage) {
        this.mainPanels = [{ component: MainViewer, props: { image } }];
        this.syncMainPanelsToViewState();
    }

    setPanel(panel: MainPanelType) {
        this.mainPanels = [panel];
        this.syncMainPanelsToViewState();
    }

    addPanel(panel: MainPanelType) {
        this.mainPanels.push(panel);
        this.syncMainPanelsToViewState();
    }

    removePanel(panel: MainPanelType) {
        this.mainPanels = this.mainPanels.filter((item) => item !== panel);
        this.syncMainPanelsToViewState();
    }

    /**
     * Open main panels from hydrated view-state, or the first instance.
     * Must run after setInstanceIDs so instances/images are in memory
     * (task grade does not preload the instances store the way /view does).
     */
    async restoreMainViewersFromViewState() {
        const pending = this.viewState?.getViewers() ?? [];
        if (pending.length) {
            const images = await Promise.all(
                pending.map(async (entry) => {
                    const instanceId = instanceIdFromImageId(entry.id);
                    const loaded = await this.getImages(instanceId);
                    return (
                        loaded.find((img) => img.image_id === entry.id) ??
                        loaded[loaded.length - 1]
                    );
                }),
            );
            const panels = images
                .filter((image): image is AbstractImage => Boolean(image))
                .map((image) => ({
                    component: MainViewer,
                    props: { image },
                }));
            if (!panels.length) return;
            if (panels.length === 1) {
                this.setPanel(panels[0]);
            } else {
                this.mainPanels = panels;
                this.syncMainPanelsToViewState();
            }
            return;
        }

        if (!this.instanceIds.length) return;
        const loaded = await this.getImages(this.instanceIds[0]);
        this.setPanel({
            component: MainViewer,
            props: { image: loaded[loaded.length - 1] },
        });
    }

    /** Keep URL/localStorage open-viewer list aligned with mainPanels. */
    syncMainPanelsToViewState() {
        if (!this.viewState) return;
        const prev = this.viewState.getViewers();
        const entries = [];
        for (const panel of this.mainPanels) {
            const image = panel.props?.image as AbstractImage | undefined;
            if (!image) continue;
            const existing = prev.find((v) => v.id === image.image_id);
            if (image.is3D && image.depth > 1) {
                const live = [...this.viewers].find(
                    (vc) => vc.image.image_id === image.image_id,
                );
                const index = live?.index ?? existing?.index;
                entries.push(
                    index !== undefined
                        ? { id: image.image_id, index }
                        : { id: image.image_id },
                );
            } else {
                entries.push({ id: image.image_id });
            }
        }
        this.viewState.setOpenViewers(entries);
    }

    findImageByImageId(imageId: string): AbstractImage | undefined {
        for (const image of this.topViewers.keys()) {
            if (image.image_id === imageId) return image;
        }
        return undefined;
    }

    getImages(instanceID: string): Promise<LoadedImages> {
        const instance = instances.get(instanceID);
        if (instance === undefined) {
            throw new Error(`Instance with id ${instanceID} not found`);
        }
        return this.loadImage(instance);
    }
}
