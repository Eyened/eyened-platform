import { ImageLoader, type LoadedImages } from "$lib/data-loading/imageLoader";
import { InstancesRepo } from "$lib/data/repos.svelte";
import { loadPhotoLocators, type PhotoLocator } from "$lib/registration/photoLocators";
import type { Registration } from "$lib/registration/registration";
import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import { AbstractImage } from "$lib/webgl/abstractImage";
import type { WebGL } from "$lib/webgl/webgl";
import { SvelteMap } from "svelte/reactivity";
import { readonly, writable, type Readable } from "svelte/store";
import type { InstanceGET } from "../../types/openapi_types";
import MainViewer from './MainViewer.svelte';

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

    private Instances = new InstancesRepo('viewer-window');

    constructor(
        public readonly webgl: WebGL,
        public readonly registration: Registration,
        public readonly creator: unknown,
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
                const instance = this.Instances.store[id] as InstanceGET | undefined;
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
        const missingIds = ids.filter((id) => !this.Instances.store[id]);
        if (missingIds.length) {
            await Promise.all(missingIds.map((id) => this.Instances.fetchOne(id, {
                with_segmentations: true,
                with_form_annotations: true,
                with_model_segmentations: true
            })));
        }

        this._instanceIds.set(ids);
    }

    destroy() {
        this.unsubscribe();

        cancelAnimationFrame(this.frame)
    }

    async loadImage(instance: InstanceGET): Promise<LoadedImages> {
        // Start loading if not already in progress
        if (!this.imagesIndex.has(instance.id)) {
            const loadPromise = this.imageLoader.load(instance).then(loadedImages => {

                // Process images once loaded
                for (const image of loadedImages) {
                    this.importPhotoLocators(image);
                }

                // Set up indices
                this.byDatasetIdentifier.set(instance.dataset_identifier, loadedImages);
                this.bySOPInstanceUID.set(instance.sop_instance_uid, loadedImages);

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
                const image_id = locator[key as keyof PhotoLocator];
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
        const instance = this.Instances.store[instanceID] as InstanceGET | undefined;
        if (instance === undefined) {
            throw new Error(`Instance with id ${instanceID} not found`);
        }
        return this.loadImage(instance);
    }


}