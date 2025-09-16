import { TagsRepo } from '$lib/data/repos.svelte';
import type { FormAnnotation } from '$lib/datamodel/formAnnotation.svelte';
import { ModelSegmentation, type Segmentation } from '$lib/datamodel/segmentation.svelte';
import { UserManager } from '$lib/usermanager.svelte';
import openAPISpec from '../../types/openapi.json';
import { apiUrl, authEnabled, fsHost, thumbnailHost } from '../config';

export type ComponentDef = {
    component: any,
    props?: any
}

export class GlobalContext {

    public userManager: UserManager;
    public tags = TagsRepo;
    public tagsLoaded: boolean = $state(false);

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

    canEdit(annotation: Segmentation | FormAnnotation | ModelSegmentation) {
        if (annotation instanceof ModelSegmentation) {
            return false;
        }
        return annotation.creator.id == this.userManager.user.id;
    }

    updateConfig(config: any) {
        this.config = { ...this.config, ...config };
    }

    get openAPISpec() {
        return openAPISpec;
    }

    get segmentationsFilter() {
        return (a: Segmentation | FormAnnotation) => {


            if (this.user.username == 'test_user') {
                // show everything for test user
                return true;
            }

            if (a.creator.id == this.user.id) {
                // always show own annotations
                return true;
            }

            if (a.creator.isHuman) {
                return this.config.showOtherAnnotationsHuman;
            } else {
                return this.config.showOtherAnnotationsMachine;
            }
        }
    }
}
