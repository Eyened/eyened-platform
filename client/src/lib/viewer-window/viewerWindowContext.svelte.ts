import { ImageLoader, type LoadedImages } from "$lib/data-loading/imageLoader";
import { loadInstances } from "$lib/datamodel/api";
import type { Creator } from "$lib/datamodel/creator.svelte";
import type { Instance } from "$lib/datamodel/instance.svelte";
import { data } from "$lib/datamodel/model";
import { loadPhotoLocators, type PhotoLocator } from "$lib/registration/photoLocators";
import type { Registration } from "$lib/registration/registration";
import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import { AbstractImage } from "$lib/webgl/abstractImage";
import type { WebGL } from "$lib/webgl/webgl";
import { SvelteMap } from "svelte/reactivity";
import MainViewer from './MainViewer.svelte';
import { readonly, writable, type Readable } from "svelte/store";

export type MainPanelType = {
    component: any;
    props: any;
}

export class ViewerWindowContext {
    
    // show/hide the browser overlay
    browserOverlay: boolean = $state(false);


    private imagesIndex = new Map<number, Promise<LoadedImages>>();
    private byDatasetIdentifier = new Map<string, LoadedImages>();
    private bySOPInstanceUID = new Map<string, LoadedImages>();

    private viewers = new Set<ViewerContext>();

    private _instanceIds = writable<number[]>([]);
    public instanceIds: Readable<number[]> = readonly(this._instanceIds);

    public mainPanels: MainPanelType[] = $state([]);

    public readonly imageLoader: ImageLoader;
    public readonly topViewers = new SvelteMap<AbstractImage, ViewerContext>();

    photoLocators = new SvelteMap<string, PhotoLocator[]>();
    photoLocatorSets: PhotoLocator[][] = $state([]);

    private frame: number = 0;
    private unsubscribe: () => void;

    constructor(
        public readonly webgl: WebGL,
        public readonly registration: Registration,
        public readonly creator: Creator,
        instanceIDs: number[] = [],
    ) {
        this.imageLoader = new ImageLoader(webgl);

        // start rendering loop
        const loop = () => {
            this.frame = requestAnimationFrame(loop);
            this.repaint();
        }
        loop();
        this.unsubscribe = this._instanceIds.subscribe((ids) => {
            for (const id of ids) {
                const instance = data.instances.get(id);
                if (instance) {
                    this.loadImage(instance);
                } else {
                    // should not happen (instance is loaded in setInstanceIDs)
                    console.warn(`Instance with id ${id} not found`);
                }
            }
        });
        this.setInstanceIDs(instanceIDs);
    }

    closeBrowserOverlay() {
        this.browserOverlay = false;
    }
    
    addViewer(viewer: ViewerContext) {
        this.viewers.add(viewer);
        return () => this.viewers.delete(viewer);
    }

    removeViewer(viewer: ViewerContext) {
        this.viewers.delete(viewer);
    }

    repaint() {
        this.webgl.clear({ left: 0, bottom: 0, width: this.webgl.canvas.width, height: this.webgl.canvas.height });
        this.viewers.forEach((viewer) => viewer.repaint());
    }

    async setInstanceIDs(ids: number[]) {
        // ensure metadata of all instances is loaded
        const missingIds = ids.filter((id) => !data.instances.has(id));
        await loadInstances(missingIds);
        this._instanceIds.set(ids);
    }

    destroy() {
        this.unsubscribe();

        cancelAnimationFrame(this.frame)
    }

    async loadImage(instance: Instance): Promise<LoadedImages> {
        // Start loading if not already in progress
        if (!this.imagesIndex.has(instance.id)) {
            const loadPromise = this.imageLoader.load(instance).then(loadedImages => {

                // Process images once loaded
                for (const image of loadedImages) {
                    this.importPhotoLocators(image);
                }

                // Set up indices
                this.byDatasetIdentifier.set(instance.datasetIdentifier, loadedImages);
                this.bySOPInstanceUID.set(instance.SOPInstanceUid, loadedImages);

                // Create viewer contexts
                for (const image of loadedImages) {
                    this.topViewers.set(image, new ViewerContext(image, this.registration));
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
            for (const key of ['enfaceImageId', 'octImageId']) {
                const image_id = locator[key];
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
    }

    setImagePanel(image: AbstractImage) {
        this.mainPanels = [{ component: MainViewer, props: { image } }];
    }

    setPanel(panel: MainPanelType) {
        this.mainPanels = [panel];
    }

    addPanel(panel: MainPanelType) {
        this.mainPanels.push(panel);
    }

    removePanel(panel: MainPanelType) {
        this.mainPanels = this.mainPanels.filter((item) => item !== panel);
    }

    getImages(instanceID: number): Promise<LoadedImages> {
        const instance = data.instances.get(instanceID);
        if (instance === undefined) {
            throw new Error(`Instance with id ${instanceID} not found`);
        }
        return this.loadImage(instance);
    }


}