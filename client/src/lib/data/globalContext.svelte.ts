import { UserManager } from '$lib/usermanager.svelte';

import type { FormAnnotationGET, ModelSegmentationGET, SearchCondition, SegmentationGET, StudySearchCondition } from '../../types/openapi_types';
import { apiUrl, authEnabled, fsHost, thumbnailHost } from '../config';
import type { Segmentation } from '../viewer-window/panelSegmentation/segmentationContext.svelte';
import { fetchFeatures, fetchFormSchemas, fetchTags } from './api';

export type ComponentDef = {
    component: any,
    props?: any
}

export class GlobalContext {

    public userManager: UserManager;
    // public tags = new TagsRepo('tags');
    // public features = new FeaturesRepo('features');
    // public formSchemas = new FormSchemasRepo('form-schemas');

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
        // user must be logged in before fetching any data
        await this.userManager.init(pathname);
        await Promise.all([
            fetchTags(),
            fetchFormSchemas(),
            fetchFeatures({ with_counts: true })
        ]);
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

    get segmentationsFilter() {
        return (a: Segmentation | FormAnnotationGET) => {

            return true



            // if (a.creator.isHuman) {
            //     return this.config.showOtherAnnotationsHuman;
            // } else {
            //     return this.config.showOtherAnnotationsMachine;
            // }
        }
    }

    /**
     * Build a Browser URL for a studies query using a single StudySearchCondition.
     */
    makeStudiesBrowserURL(condition: StudySearchCondition): string {
        const params = new URLSearchParams();
        params.set('page', '0');
        params.set('limit', '10');
        params.set('conditions', this._encodeSingleCondition(condition));
        params.set('order_by', 'Study Date');
        params.set('order', 'ASC');
        params.set('queryMode', 'studies');
        params.set('displayMode', 'study');
        params.set('filterMode', 'advanced');
        return `/?${params.toString()}`;
    }

    /**
     * Build a Browser URL for an instances query using a single SearchCondition.
     */
    makeInstancesBrowserURL(condition: SearchCondition): string {
        const params = new URLSearchParams();
        params.set('page', '0');
        params.set('limit', '100');
        params.set('conditions', this._encodeSingleConditionExtended(condition as any));
        params.set('order_by', 'Study Date');
        params.set('order', 'ASC');
        params.set('queryMode', 'instances');
        params.set('displayMode', 'instance');
        params.set('filterMode', 'advanced');
        return `/?${params.toString()}`;
    }

    // Private helper, compatible with both condition types
    private _encodeSingleCondition(
        condition: { variable: string; operator: string; value: string | number | string[] | null }
    ): string {
        const serializeValue = (v: string | number | string[] | null) => JSON.stringify(v);
        const encodedVariable = encodeURIComponent(condition.variable);
        const encodedOperator = encodeURIComponent(condition.operator);
        const encodedValue = encodeURIComponent(serializeValue(condition.value ?? null));
        return `${encodedVariable}:${encodedOperator}:${encodedValue}`;
    }

    private _encodeSingleConditionExtended(
        condition: { variable: string; operator: string; value: string | number | string[] | null; type?: 'default' | 'attribute'; model?: string; feature?: string }
    ): string {
        const serializeValue = (v: string | number | string[] | null) => JSON.stringify(v);
        const encodedVariable = encodeURIComponent(condition.variable);
        const encodedOperator = encodeURIComponent(condition.operator);
        const encodedValue = encodeURIComponent(serializeValue(condition.value ?? null));
        const encodedType = encodeURIComponent(condition.type ?? 'default');
        const encodedModel = encodeURIComponent((condition.type === 'attribute' ? condition.model ?? '' : ''));
        const encodedFeature = encodeURIComponent((condition.type === 'attribute' ? condition.feature ?? '' : ''));
        return `${encodedVariable}:${encodedOperator}:${encodedValue}:${encodedType}:${encodedModel}:${encodedFeature}`;
    }
}
