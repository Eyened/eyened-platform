import type {
	FeatureGET, FeaturePATCH, FeaturePUT,
	FormAnnotationGET, FormAnnotationPUT,
	FormSchemaGET,
	InstanceGET,
	ModelSegmentationGET,
	SegmentationGET, SegmentationPATCH, SegmentationPOST,
	SeriesGET,
	StudyGET,
	TagGET, TagPATCH, TagPUT
} from '../../types/openapi_types';
import { UserManager } from '../usermanager.svelte';
import {
	Feature,
	FormAnnotation,
	FormSchema,
	Instance,
	ModelSegmentation,
	Segmentation,
	Series,
	Study,
	Tag
} from './models.svelte';
import { GlobalRepos, Repo } from './repo.svelte';

export type ComponentDef = {
	component: any;
	props?: any;
};

/**
 * GlobalContext - simple, clean repo management
 * All repos are just SvelteMap<id, ClassInstance>
 */
export class GlobalContext extends GlobalRepos {
	// User management
	public userManager: UserManager;

	// Simple repos - just maps of class instances!
	instances = new Repo<InstanceGET, Instance>('/instances', Instance);
	studies = new Repo<StudyGET, Study>('/studies', Study);
	series = new Repo<SeriesGET, Series>('/series', Series);
	tags = new Repo<TagGET, Tag, TagPUT, TagPATCH>('/tags', Tag);
	features = new Repo<FeatureGET, Feature, FeaturePUT, FeaturePATCH>('/features', Feature);
	formSchemas = new Repo<FormSchemaGET, FormSchema>('/form-schemas', FormSchema);
	segmentations = new Repo<SegmentationGET, Segmentation, SegmentationPOST, SegmentationPATCH>('/segmentations', Segmentation);
	modelSegmentations = new Repo<ModelSegmentationGET, ModelSegmentation>('/model-segmentations', ModelSegmentation);
	formAnnotations = new Repo<FormAnnotationGET, FormAnnotation, FormAnnotationPUT, FormAnnotationPUT>('/form-annotations', FormAnnotation);

	// UI state
	public popupComponent: ComponentDef | null = $state(null);
	public dialogue: ComponentDef | string | null = $state(null);
	public showUserMenu: boolean = $state(false);

	public formShortcut: string | null = $state('WARMGS');
	public config: any = $state({
		showOtherAnnotationsHuman: true,
		showOtherAnnotationsMachine: true
	});

	constructor() {
		super();
		// Set singleton for items to access repos
		GlobalRepos.instance = this;
		
		this.userManager = new UserManager();
		console.log(`Loaded GlobalContext (data2 - new implementation)`);
	}

	async init(pathname: string) {
		await Promise.all([
			this.userManager.init(pathname),
			this.tags.fetchAll(),
			this.formSchemas.fetchAll(),
			this.features.fetchAll({ with_counts: true })
		]);
	}

	get user() {
		return this.userManager.user;
	}

	// Derived reactive properties - clean and simple!
	get studyTags() {
		return this.tags.all.filter(t => t.tagType === 'Study');
	}

	get instanceTags() {
		return this.tags.all.filter(t => t.tagType === 'ImageInstance');
	}

	get formAnnotationTags() {
		return this.tags.all.filter(t => t.tagType === 'Annotation');
	}

	setPopup(component: ComponentDef | null) {
		this.popupComponent = component;
	}

	canEdit(annotation: { annotation_type?: string; creator: { id: number } }) {
		if (annotation.annotation_type === 'model_segmentation') {
			return false;
		}
		return annotation.creator.id === this.userManager.user.id;
	}

	updateConfig(config: any) {
		this.config = { ...this.config, ...config };
	}

	/**
	 * Build a Browser URL for a studies query
	 */
	makeStudiesBrowserURL(condition: any): string {
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
	 * Build a Browser URL for an instances query
	 */
	makeInstancesBrowserURL(condition: any): string {
		const params = new URLSearchParams();
		params.set('page', '0');
		params.set('limit', '100');
		params.set('conditions', this._encodeSingleCondition(condition));
		params.set('order_by', 'Study Date');
		params.set('order', 'ASC');
		params.set('queryMode', 'instances');
		params.set('displayMode', 'instance');
		params.set('filterMode', 'advanced');
		return `/?${params.toString()}`;
	}

	private _encodeSingleCondition(
		condition: { variable: string; operator: string; value: string | number | string[] | null }
	): string {
		const serializeValue = (v: string | number | string[] | null) => JSON.stringify(v);
		const encodedVariable = encodeURIComponent(condition.variable);
		const encodedOperator = encodeURIComponent(condition.operator);
		const encodedValue = encodeURIComponent(serializeValue(condition.value ?? null));
		return `${encodedVariable}:${encodedOperator}:${encodedValue}`;
	}
}

