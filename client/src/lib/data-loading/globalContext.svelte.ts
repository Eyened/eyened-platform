import type { Annotation } from '$lib/datamodel/annotation.svelte';
import type { FormAnnotation } from '$lib/datamodel/formAnnotation.svelte';
import { UserManager } from '$lib/usermanager';

export type ComponentDef = {
    component: any,
    props?: any
}


export class GlobalContext {

    public userManager: UserManager;

    public popupComponent: ComponentDef | null = $state(null);

    public formShortcut: string | null = $state('WARMGS');
    public config: any = $state({
        showOtherAnnotationsHuman: true,
        showOtherAnnotationsMachine: true,
    });

    constructor() {
        this.userManager = new UserManager()
    }

    async init(pathname: string) {
        await this.userManager.init(pathname);
    }

    get creator() {
        return this.userManager.creator;
    }

    setPopup(component: ComponentDef | null) {
        this.popupComponent = component;
    }

    canEdit(annotation: Annotation | FormAnnotation) {
        return annotation.creator.id == this.userManager.creator.id;
    }

    updateConfig(config: any) {
        this.config = { ...this.config, ...config };
    }

    get annotationsFilter() {
        return (a: Annotation | FormAnnotation) => {
            
            // if (a.id != 1962178) return false;
            if (a.feature && ['Form', 'Registration', 'ETDRS grid', 'Arteriovenous (AV) nicking'].includes(a.feature.name)) {
                return false;
            }

            if (this.creator.name == 'test_user') {
                // show everything for test user
                return true;
            }

            if (a.creator.id == this.creator.id) {
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
