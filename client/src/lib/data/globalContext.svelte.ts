import { FeaturesRepo, FormSchemasRepo, TagsRepo } from '$lib/data/repos.svelte';
import { UserManager } from '$lib/usermanager.svelte';
import openAPISpec from '../../types/openapi.json';
import type { FormAnnotationGET, ModelSegmentationGET, SegmentationGET } from '../../types/openapi_types';
import { apiUrl, authEnabled, fsHost, thumbnailHost } from '../config';

export type ComponentDef = {
    component: any,
    props?: any
}

export class GlobalContext {

    public userManager: UserManager;
    public tags = new TagsRepo('tags');
    public tagsLoaded: boolean = $state(false);
    public features = new FeaturesRepo('features');
    public featuresLoaded: boolean = $state(false);
    public formSchemas = new FormSchemasRepo('form-schemas');
    public formSchemasLoaded: boolean = $state(false);

    public popupComponent: ComponentDef | null = $state(null);
    public dialogue: ComponentDef | string | null = $state(null);
    public showUserMenu: boolean = $state(false);

    public formShortcut: string | null = $state('WARMGS');
    public config: any = $state({
        showOtherAnnotationsHuman: true,
        showOtherAnnotationsMachine: true,
    });

    constructor() {
        this.userManager = new UserManager()
        console.log(`Loaded GlobalContext`)
        console.log(`apiUrl: ${apiUrl}`)
        console.log(`fsHost: ${fsHost}`)
        console.log(`thumbnailHost: ${thumbnailHost}`)
        console.log(`authEnabled: ${authEnabled}`)
        console.log(import.meta.env.PUBLIC_AUTH_DISABLED)
    }

    async init(pathname: string) {
        await this.userManager.init(pathname);
        await this.tags.fetchAll();
        this.tagsLoaded = true;
    }

    get user() {
        return this.userManager.user;
    }

    setPopup(component: ComponentDef | null) {
        this.popupComponent = component;
    }

    canEdit(annotation: SegmentationGET | FormAnnotationGET | ModelSegmentationGET) {
        if (annotation.annotation_type == 'model_segmentation') {
            return false;
        }
        return annotation.creator.id == this.userManager.user.id;
    }

    updateConfig(config: any) {
        this.config = { ...this.config, ...config };
    }

    async ensureFeaturesLoaded() {
        if (!this.featuresLoaded) {
            await this.features.fetchAll();
            this.featuresLoaded = true;
        }
    }

    async ensureFormSchemasLoaded() {
        if (!this.formSchemasLoaded) {
            await this.formSchemas.fetchAll();
            this.formSchemasLoaded = true;
        }
    }

    get openAPISpec() {
        return openAPISpec;
    }

    get segmentationsFilter() {
        return (a: SegmentationGET | FormAnnotationGET) => {


            if (this.user.username == 'test_user') {
                // show everything for test user
                return true;
            }

            if (a.creator.id == this.user.id) {
                // always show own annotations
                return true;
            }

            // if (a.creator.isHuman) {
            //     return this.config.showOtherAnnotationsHuman;
            // } else {
            //     return this.config.showOtherAnnotationsMachine;
            // }
        }
    }
}
