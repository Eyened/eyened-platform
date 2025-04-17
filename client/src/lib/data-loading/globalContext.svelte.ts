import type { Annotation } from '$lib/datamodel/annotation';
import type { Creator } from '$lib/datamodel/creator';
import type { FormAnnotation } from '$lib/datamodel/formAnnotation';
import type { UserManager } from '$lib/usermanager';

export type ComponentDef = {
    component: any,
    props?: any
}


export class GlobalContext {

    public popupComponent: ComponentDef | null = $state(null);

    public formShortcut: string | null = $state('WARMGS');
    public config: any = $state({
        showOtherAnnotationsHuman: true,
        showOtherAnnotationsMachine: true,
    });

    constructor(readonly userManager: UserManager, readonly creator: Creator) { }

    setPopup(component: ComponentDef | null) {
        this.popupComponent = component;
    }

    canEdit(annotation: Annotation | FormAnnotation) {
        return annotation.creator.id == this.userManager.CreatorID;
    }

    updateConfig(config: any) {
        this.config = { ...this.config, ...config };
    }

    get annotationsFilter() {
        return (a: { creator: Creator }) => {
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
