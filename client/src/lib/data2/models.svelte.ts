import type {
	FeatureGET, FeaturePATCH,
	FormAnnotationGET, FormAnnotationPUT,
	FormSchemaGET,
	InstanceGET,
	ModelSegmentationGET,
	SegmentationGET, SegmentationPATCH,
	SeriesGET,
	StudyGET,
	TagGET, TagPATCH
} from '../../types/openapi_types';
import { RepoItem } from './repo.svelte';

/**
 * Instance - represents an image instance
 */
export class Instance extends RepoItem<InstanceGET> {
	// Direct property access - no ugly .$ accessor!
	get modality() { return this._data.modality; }
	get dicomModality() { return this._data.dicom_modality; }
	get laterality() { return this._data.laterality; }
	get tags() { return this._data.tags; }
	get rows() { return this._data.rows; }
	get columns() { return this._data.columns; }
	get nrOfFrames() { return this._data.nr_of_frames; }
	get datasetIdentifier() { return this._data.dataset_identifier; }
	get sopInstanceUid() { return this._data.sop_instance_uid; }
	get thumbnailPath() { return this._data.thumbnail_path; }
	
	// Related objects - embedded in the data
	get seriesId() { return this._data.series.id; }
	get studyId() { return this._data.study.id; }
	get patientId() { return this._data.patient.id; }
	
	// Related objects - access other repos via base class
	get series() {
		return this.repos.series.get(this.seriesId);
	}
	
	get study() {
		return this.repos.studies.get(this.studyId);
	}
	
	get patient() {
		// TODO: Add patient repo
		return undefined;
	}
	
	// Collections
	get segmentations() {
		return this.repos.segmentations.all.filter(
			seg => seg.instanceId === this.id
		);
	}
	
	get modelSegmentations() {
		return this.repos.modelSegmentations.all.filter(
			seg => seg.instanceId === this.id
		);
	}
	
	// Custom methods
	async tag(tagId: number): Promise<void> {
		const { api } = await import('../api/client');
		const { data } = await api.POST('/instances/{instance_id}/tags' as any, {
			params: { path: { instance_id: Number(this.id) } } as any,
			body: { tag_id: tagId } as any
		});
		this.updateLocal({ tags: [...this.tags, data] } as any);
	}
	
	async untag(tagId: number): Promise<void> {
		const { api } = await import('../api/client');
		await api.DELETE('/instances/{instance_id}/tags/{tag_id}' as any, {
			params: { path: { instance_id: Number(this.id), tag_id: tagId } } as any
		});
		this.updateLocal({ 
			tags: this.tags.filter(t => t.id !== tagId) 
		} as any);
	}
}

/**
 * Series
 */
export class Series extends RepoItem<SeriesGET> {
	get laterality() { return this._data.laterality; }
	get seriesNumber() { return this._data.series_number; }
	get seriesInstanceUid() { return this._data.series_instance_uid; }
	get instanceIds() { return this._data.instance_ids ?? []; }
	
	// Note: SeriesGET doesn't have embedded study, need to get from instances
	get study() {
		const instance = this.repos.instances.all.find(inst => inst.seriesId === this.id);
		return instance?.study;
	}
	
	get instances() {
		return this.repos.instances.all.filter(
			inst => inst.seriesId === this.id
		);
	}
}

/**
 * Study
 */
export class Study extends RepoItem<StudyGET> {
	get description() { return this._data.description; }
	get date() { return this._data.date; }
	get age() { return this._data.age; }
	get tags() { return this._data.tags; }
	get studyInstanceUid() { return this._data.study_instance_uid; }
	get project() { return this._data.project; }
	
	// Embedded patient/project meta
	get patientId() { return this._data.patient.id; }
	get projectId() { return this._data.project.id; }
	
	get patient() {
		// TODO: Add patient repo
		return undefined;
	}
	
	get series() {
		return this._data.series ?? [];
	}
	
	get instances() {
		return this.repos.instances.all.filter(
			inst => inst.studyId === this.id
		);
	}
	
	async tag(tagId: number): Promise<void> {
		const { api } = await import('../api/client');
		const { data } = await api.POST('/studies/{study_id}/tags' as any, {
			params: { path: { study_id: Number(this.id) } } as any,
			body: { tag_id: tagId } as any
		});
		this.updateLocal({ tags: [...this.tags, data] } as any);
	}
	
	async untag(tagId: number): Promise<void> {
		const { api } = await import('../api/client');
		await api.DELETE('/studies/{study_id}/tags/{tag_id}' as any, {
			params: { path: { study_id: Number(this.id), tag_id: tagId } } as any
		});
		this.updateLocal({ 
			tags: this.tags.filter(t => t.id !== tagId) 
		} as any);
	}
}

/**
 * Tag
 */
export class Tag extends RepoItem<TagGET> {
	get name() { return this._data.name; }
	get tagType() { return this._data.tag_type; }
	get description() { return this._data.description; }
	get creator() { return this._data.creator; }
	get dateInserted() { return this._data.date_inserted; }
	
	async star(): Promise<void> {
		const { api } = await import('../api/client');
		await api.POST('/tags/{tag_id}/star' as any, {
			params: { path: { tag_id: Number(this.id) } } as any
		});
		// Could optimistically update if needed
	}
	
	async unstar(): Promise<void> {
		const { api } = await import('../api/client');
		await api.DELETE('/tags/{tag_id}/star' as any, {
			params: { path: { tag_id: Number(this.id) } } as any
		});
	}
	
	async save(patch?: Partial<TagPATCH>): Promise<void> {
		const updated = await this.repos.tags.update(this.id, patch ?? {});
		this._replaceData(updated._data);
	}
}

/**
 * Feature
 */
export class Feature extends RepoItem<FeatureGET> {
	get name() { return this._data.name; }
	get subfeatures() { return this._data.subfeatures; }
	get subfeatureIds() { return this._data.subfeature_ids; }
	get dateInserted() { return this._data.date_inserted; }
	get segmentationCount() { return this._data.segmentation_count; }
	
	async save(patch?: Partial<FeaturePATCH>): Promise<void> {
		const updated = await this.repos.features.update(this.id, patch ?? {});
		this._replaceData(updated._data);
	}
}

/**
 * FormSchema
 */
export class FormSchema extends RepoItem<FormSchemaGET> {
	get name() { return this._data.name; }
	get schema() { return this._data.schema; }
}

/**
 * Segmentation with special data methods
 */
export class Segmentation extends RepoItem<SegmentationGET> {
	get instanceId() { return this._data.image_instance_id; }
	get tags() { return this._data.tags; }
	get creatorId() { return this._data.creator.id; }
	get creator() { return this._data.creator; }
	get dataType() { return this._data.data_type; }
	get dataRepresentation() { return this._data.data_representation; }
	get threshold() { return this._data.threshold; }
	get annotationType() { return this._data.annotation_type; }
	
	// Embedded feature
	get featureId() { return this._data.feature.id; }
	get featureName() { return this._data.feature.name; }
	
	get instance() {
		return this.repos.instances.get(this.instanceId);
	}
	
	get feature() {
		return this.repos.features.get(this.featureId);
	}
	
	async getData(params?: { axis?: number; scan_nr?: number }) {
		const { api } = await import('../api/client');
		const { decodeNpy } = await import('../utils/npy_loader');
		const res = await api.GET('/segmentations/{segmentation_id}/data', {
			params: {
				path: { segmentation_id: Number(this.id) },
				query: params ?? {}
			},
			parseAs: "arrayBuffer"
		});
		return decodeNpy(res.data!);
	}
	
	async updateData(arrayBuffer: ArrayBuffer, params?: { axis?: number; scan_nr?: number }) {
		const { apiUrl } = await import('../config');
		const url = `${apiUrl}/segmentations/${this.id}/data?axis=${params?.axis}&scan_nr=${params?.scan_nr}`;
		await fetch(url, {
			method: 'PUT',
			credentials: 'include',
			headers: { 'Content-Type': 'application/octet-stream' },
			body: arrayBuffer
		});
	}
	
	async tag(tagId: number): Promise<void> {
		const { api } = await import('../api/client');
		const { data } = await api.POST('/segmentations/{segmentation_id}/tags' as any, {
			params: { path: { segmentation_id: Number(this.id) } } as any,
			body: { tag_id: tagId } as any
		});
		this.updateLocal({ tags: [...this.tags, data] } as any);
	}
	
	async untag(tagId: number): Promise<void> {
		const { api } = await import('../api/client');
		await api.DELETE('/segmentations/{segmentation_id}/tags/{tag_id}' as any, {
			params: { path: { segmentation_id: Number(this.id), tag_id: tagId } } as any
		});
		this.updateLocal({ 
			tags: this.tags.filter(t => t.id !== tagId) 
		} as any);
	}
	
	async save(patch?: Partial<SegmentationPATCH>): Promise<void> {
		const updated = await this.repos.segmentations.update(this.id, patch ?? {});
		this._replaceData(updated._data);
	}
}

/**
 * ModelSegmentation
 */
export class ModelSegmentation extends RepoItem<ModelSegmentationGET> {
	get instanceId() { return this._data.image_instance_id; }
	get tags() { return this._data.tags; }
	get dataType() { return this._data.data_type; }
	get dataRepresentation() { return this._data.data_representation; }
	get threshold() { return this._data.threshold; }
	get annotationType() { return this._data.annotation_type; }
	
	// Embedded feature and model/creator
	get featureId() { return this._data.feature.id; }
	get featureName() { return this._data.feature.name; }
	get modelId() { return this._data.creator.id; }
	get creator() { return this._data.creator; }
	
	get instance() {
		return this.repos.instances.get(this.instanceId);
	}
	
	get feature() {
		return this.repos.features.get(this.featureId);
	}
	
	async getData(params?: { axis?: number; scan_nr?: number }) {
		const { api } = await import('../api/client');
		const { decodeNpy } = await import('../utils/npy_loader');
		const res = await api.GET('/model-segmentations/{model_segmentation_id}/data', {
			params: {
				path: { model_segmentation_id: Number(this.id) },
				query: params ?? {}
			},
			parseAs: "arrayBuffer"
		});
		return decodeNpy(res.data!);
	}
	
	async tag(tagId: number): Promise<void> {
		const { api } = await import('../api/client');
		const { data } = await api.POST('/model-segmentations/{segmentation_id}/tags' as any, {
			params: { path: { segmentation_id: Number(this.id) } } as any,
			body: { tag_id: tagId } as any
		});
		this.updateLocal({ tags: [...this.tags, data] } as any);
	}
	
	async untag(tagId: number): Promise<void> {
		const { api } = await import('../api/client');
		await api.DELETE('/model-segmentations/{segmentation_id}/tags/{tag_id}' as any, {
			params: { path: { segmentation_id: Number(this.id), tag_id: tagId } } as any
		});
		this.updateLocal({ 
			tags: this.tags.filter(t => t.id !== tagId) 
		} as any);
	}
}

/**
 * FormAnnotation
 */
export class FormAnnotation extends RepoItem<FormAnnotationGET> {
	get formSchemaId() { return this._data.form_schema_id; }
	get instanceId() { return this._data.image_instance_id; }
	get studyId() { return this._data.study_id; }
	get patientId() { return this._data.patient_id; }
	get tags() { return this._data.tags; }
	get creator() { return this._data.creator; }
	
	get formSchema() {
		return this.repos.formSchemas.get(this.formSchemaId);
	}
	
	get instance() {
		return this.instanceId ? this.repos.instances.get(this.instanceId) : undefined;
	}
	
	get study() {
		return this.studyId ? this.repos.studies.get(this.studyId) : undefined;
	}
	
	async getValue() {
		const { api } = await import('../api/client');
		const res = await api.GET('/form-annotations/{form_annotation_id}/value', {
			params: { path: { form_annotation_id: Number(this.id) } }
		});
		return res.data as unknown;
	}
	
	async setValue(value: unknown) {
		const { api } = await import('../api/client');
		await api.PUT('/form-annotations/{form_annotation_id}/value', {
			params: { path: { form_annotation_id: Number(this.id) } },
			body: value as any
		});
	}
	
	async tag(tagId: number): Promise<void> {
		const { api } = await import('../api/client');
		const { data } = await api.POST('/form-annotations/{annotation_id}/tags' as any, {
			params: { path: { annotation_id: Number(this.id) } } as any,
			body: { tag_id: tagId } as any
		});
		this.updateLocal({ tags: [...this.tags, data] } as any);
	}
	
	async untag(tagId: number): Promise<void> {
		const { api } = await import('../api/client');
		await api.DELETE('/form-annotations/{annotation_id}/tags/{tag_id}' as any, {
			params: { path: { annotation_id: Number(this.id), tag_id: tagId } } as any
		});
		this.updateLocal({ 
			tags: this.tags.filter(t => t.id !== tagId) 
		} as any);
	}
	
	async save(patch?: Partial<FormAnnotationPUT>): Promise<void> {
		const updated = await this.repos.formAnnotations.update(this.id, patch ?? {});
		this._replaceData(updated._data);
	}
}

